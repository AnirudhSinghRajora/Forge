"""FastAPI app: every route in the build contract under /api, plus the built web app at /."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, get_args

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import AfterValidator, BaseModel, StringConstraints
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.agent import parse as report_parse
from app import disclosures, errors, limits
from app.agent import advisory, current_text, rubric, runner
from app.agent.plot import PlotRejected, check_pin, validate_polygon
from app.config import VERSION, get_settings
from app.db import Action, Case, EvidenceRow, Plot, Run, RunEvent, init_db, session_scope
from app.evidence.schema import EventType, Evidence

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for _handler in logging.getLogger().handlers:
    _handler.setFormatter(errors.ScrubbingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
# httpx logs every request's URL at INFO, and a weather URL can carry the API key.
logging.getLogger("httpx").setLevel(logging.WARNING)

EVENT_TYPES = set(get_args(EventType))
INSURED_VALUES = {"yes", "no", "unknown"}
CROP_STAGES = {"standing", "cut_and_spread", "harvested_stored", "unknown"}
QUESTIONS = {
    "crop": {"hi": "खेत में कौन सी फ़सल थी?", "en": "Which crop was in the field?",
             "te": "పొలంలో ఏ పంట ఉంది?"},
    "event_type": {"hi": "क्या हुआ था: ओले, बारिश, बाढ़, तूफ़ान या कुछ और?",
                   "en": "What happened: hail, rain, flood, storm or something else?",
                   "te": "ఏం జరిగింది: వడగళ్లు, వర్షం, వరద, తుఫాను లేదా ఇంకేదైనా?"},
    "event_date": {"hi": "यह किस तारीख़ को हुआ था?", "en": "On what date did this happen?",
                   "te": "ఇది ఏ తేదీన జరిగింది?"},
    "insured": {"hi": "क्या इस मौसम में आपकी फ़सल का बीमा है? ऋण वाले किसान अपने बैंक से पूछ सकते हैं।",
                "en": "Is this crop insured this season? If you have a crop loan, your bank can tell you.",
                "te": "ఈ సీజన్‌లో మీ పంటకు బీమా ఉందా? పంట రుణం ఉంటే మీ బ్యాంకు చెప్పగలదు."},
    "crop_stage": {"hi": "घटना के समय फ़सल खड़ी थी, कटकर खेत में सूख रही थी, या कटकर रखी जा चुकी थी?",
                   "en": "Was the crop standing, cut and drying in the field, or already stored?",
                   "te": "ఆ సమయంలో పంట నిలబడి ఉందా, కోసి పొలంలో ఆరబెట్టారా, లేక నిల్వ చేశారా?"},
    "plot": {"hi": "कृपया नक्शे पर अपने खेत की सीमा बनाएँ।", "en": "Please outline your field on the map.",
             "te": "దయచేసి మ్యాప్‌లో మీ పొలం సరిహద్దు గీయండి."},
    "transcript": {"hi": "आवाज़ समझ नहीं आई। कृपया दोबारा बोलें या लिखकर बताएँ।",
                   "en": "The voice note could not be understood. Please try again or type it.",
                   "te": "వాయిస్ అర్థం కాలేదు. దయచేసి మళ్లీ చెప్పండి లేదా టైప్ చేయండి."},
}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    if not get_settings().public_web_url:
        log.warning("PUBLIC_WEB_URL is not set: PDF QR codes and verify links use each request's own origin")
    closed = runner.recover_interrupted()
    if closed:
        log.warning("closed %d runs interrupted by the last restart", closed)
    from app import verify

    verify.recover_interrupted()
    stop_scheduler = None
    try:
        from app import jobs

        threading.Thread(target=jobs.archive_alerts_safe, daemon=True, name="sachet-boot").start()
        if get_settings().enable_scheduler:
            stop_scheduler = jobs.start_scheduler()
    except Exception:  # background jobs must never stop the API from serving
        log.exception("background jobs could not start")
    yield
    if stop_scheduler:
        stop_scheduler()


MAX_AUDIO_BODY_BYTES = 25 * 1024 * 1024
MAX_AUDIO_BYTES = 24 * 1024 * 1024
MAX_JSON_BODY_BYTES = 64 * 1024
MAX_AFTER = 2**53  # larger than any event sequence, and small enough for every database integer
AUDIO_CHUNK_BYTES = 1024 * 1024


def _body_limit(method: str, path: str) -> int:
    """Only creating a case can carry a voice note. Every other body is a small form or JSON."""
    return MAX_AUDIO_BODY_BYTES if method == "POST" and path == "/api/cases" else MAX_JSON_BODY_BYTES


class BodyLimit:
    """Refuses an oversized body, whether it announces its length or streams past the limit."""

    def __init__(self, inner):
        self.inner = inner

    @staticmethod
    async def _refuse(send) -> None:
        body = json.dumps({"detail": {
            "code": "body_too_large",
            "message_hi": "यह भेजी गई सामग्री बहुत बड़ी है।",
            "message_en": "What was sent is too large.",
            "message_te": "పంపినది చాలా పెద్దది.",
        }}, ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.inner(scope, receive, send)
            return
        limit = _body_limit(scope["method"], scope["path"])
        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > limit:
            await self._refuse(send)
            return
        seen = 0
        over = False
        started = False

        async def counted_receive():
            nonlocal seen, over
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    over = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            nonlocal started
            if over:
                return  # whatever the route made of a cut-off body, the answer is the 413 below
            started = True
            await send(message)

        try:
            await self.inner(scope, counted_receive, guarded_send)
        except Exception:
            if not over:
                raise
        if over and not started:
            await self._refuse(send)


app = FastAPI(title="FasalSaakshi", version=VERSION, lifespan=lifespan)
app.add_middleware(BodyLimit)


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    ref = errors.report(log, "unhandled error", exc)
    return JSONResponse(status_code=500, content={"detail": f"internal error (ref {ref})", "error_ref": ref})


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Says what is wrong and never echoes the input, which can be huge or not even valid text."""
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": [str(part) for part in e.get("loc", ())], "msg": str(e.get("msg", "invalid")), "type": str(e.get("type", ""))}
        for e in exc.errors()
    ]})


# Helpers


def _clean(value: str) -> str:
    """A lone surrogate cannot be stored or sent, and a NUL cannot be stored in Postgres."""
    if any(c == "\x00" or "\ud800" <= c <= "\udfff" for c in value):
        raise ValueError("contains characters that are not valid text")
    return value


def _text(max_length: int):
    return Annotated[str, StringConstraints(max_length=max_length), AfterValidator(_clean)]


def _message(hi: str, en: str, te: str, code: str) -> dict:
    return {"code": code, "message_hi": hi, "message_en": en, "message_te": te}


def _check_form_text(value: str | None, max_length: int, name: str) -> None:
    if value is None:
        return
    try:
        _clean(value)
    except ValueError as exc:
        raise HTTPException(422, detail=f"{name} is not valid text") from exc
    if len(value) > max_length:
        raise HTTPException(422, detail=_message(
            f"यह बहुत लंबा है। कृपया {max_length} अक्षरों में लिखें।",
            f"This is too long. Please keep it under {max_length} characters.",
            f"ఇది చాలా పొడవుగా ఉంది. దయచేసి {max_length} అక్షరాల్లో రాయండి.",
            "text_too_long",
        ))


def _bad_audio() -> HTTPException:
    return HTTPException(415, detail=_message(
        "यह आवाज़ की फ़ाइल नहीं लगती। कृपया दोबारा रिकॉर्ड करें या लिखकर बताएँ।",
        "This does not look like a voice recording. Please record again or type it.",
        "ఇది వాయిస్ రికార్డింగ్ లాగా లేదు. దయచేసి మళ్ళీ రికార్డ్ చేయండి లేదా టైప్ చేయండి.",
        "audio_not_recognised",
    ))


def _is_audio_container(head: bytes) -> bool:
    """The containers browsers record into, for a client that labelled the upload generically."""
    return (
        head.startswith((b"\x1aE\xdf\xa3", b"OggS", b"ID3", b"fLaC", b"\xff\xfb", b"\xff\xf3", b"\xff\xf1", b"\xff\xf9"))
        or (head[:4] == b"RIFF" and head[8:12] == b"WAVE")
        or head[4:8] == b"ftyp"
    )


def _read_audio(audio: UploadFile) -> bytes:
    """Read in chunks up to the cap. Accepted as audio by its declared type or by its first bytes."""
    data = bytearray()
    while chunk := audio.file.read(AUDIO_CHUNK_BYTES):
        data += chunk
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(413, detail=_message(
                "आवाज़ की यह रिकॉर्डिंग बहुत लंबी है। कृपया छोटी रिकॉर्डिंग भेजें या लिखकर बताएँ।",
                "This recording is too long. Please send a shorter one or type it.",
                "ఈ రికార్డింగ్ చాలా పెద్దది. దయచేసి చిన్నది పంపండి లేదా టైప్ చేయండి.",
                "audio_too_large",
            ))
    declared = (audio.content_type or "").split(";")[0].strip().lower()
    if not declared.startswith("audio/") and not _is_audio_container(bytes(data[:16])):
        raise _bad_audio()
    return bytes(data)


def _date_error(when: date) -> None:
    if (problem := report_parse.event_date_problem(when)) is not None:
        raise HTTPException(422, detail=report_parse.EVENT_DATE_MESSAGES[problem])


def _get_case(s, case_id: str) -> Case:
    case = s.get(Case, case_id) if len(case_id) <= 64 and "\x00" not in case_id else None
    if case is None:
        raise HTTPException(404, detail="unknown case")
    return case


def _case_dict(s, case: Case) -> dict:
    plot = s.scalar(select(Plot).where(Plot.case_id == case.id))
    runs = s.scalars(
        select(Run).where(Run.case_id == case.id).order_by(Run.started_at.desc())
    ).all()
    latest = runs[0] if runs else None
    needs = list(case.needs or [])
    return {
        "id": case.id,
        "lat": case.lat,
        "lon": case.lon,
        "lang": case.lang,
        "transcript": case.transcript,
        "crop": case.crop,
        "event_type": case.event_type,
        "event_date": case.event_date.isoformat() if case.event_date else None,
        "event_time": case.event_time,
        "insured": case.insured,
        "crop_stage": case.crop_stage,
        "date_source": case.date_source,
        "proposed_event_date": case.proposed_event_date.isoformat()
        if case.proposed_event_date else None,
        "status": case.status,
        "district": case.district,
        "state": case.state,
        "parsed": case.parsed,
        "needs": needs,
        "questions": {n: QUESTIONS[n] for n in needs if n in QUESTIONS},
        "plot": {
            "geometry": plot.geometry,
            "area_ha": plot.area_ha,
            "centroid": [plot.centroid_lon, plot.centroid_lat],
            "crs": plot.crs,
            "warnings": plot.warnings,
        } if plot else None,
        "active_run_id": latest.id if latest and latest.status in runner.ACTIVE else None,
        "latest_run": {
            "id": latest.id, "status": latest.status, "trigger": latest.trigger,
            "started_at": latest.started_at.isoformat(),
            "finished_at": latest.finished_at.isoformat() if latest.finished_at else None,
            "error": errors.public_text(latest.error),
        } if latest else None,
        "created_at": case.created_at.isoformat(),
        "updated_at": case.updated_at.isoformat(),
    }


def _action_dict(action: Action) -> dict:
    return {
        "id": action.id, "type": action.type, "payload": action.payload, "status": action.status,
        "due_at": action.due_at.isoformat() if action.due_at else None,
        "created_at": action.created_at.isoformat(),
    }


def _latest_evidence(s, case_id: str) -> EvidenceRow | None:
    """The newest sealed record, else the newest with a verdict, else whatever exists. An unsealed
    re-run, finished or interrupted, never displaces a sealed result; the first run of a case shows
    its verdict at once while its exhibits fill in."""
    rows = s.scalars(
        select(EvidenceRow).where(EvidenceRow.case_id == case_id)
        .order_by(EvidenceRow.created_at.desc())
    ).all()
    return (
        next((r for r in rows if r.evidence_hash), None)
        or next((r for r in rows if r.verdict_level), None)
        or (rows[0] if rows else None)
    )


def _route_needs(insured: str | None, crop_stage: str | None) -> list[str]:
    """Reported in `needs` when missing, but never a reason to block an investigation."""
    needs = []
    if insured not in ("yes", "no"):
        needs.append("insured")
    if crop_stage not in ("standing", "cut_and_spread", "harvested_stored"):
        needs.append("crop_stage")
    return needs


def _refresh_needs(s, case: Case) -> None:
    needs = report_parse.needs_for(case.crop, case.event_type, case.event_date)
    needs.extend(_route_needs(case.insured, case.crop_stage))
    if s.scalar(select(Plot.id).where(Plot.case_id == case.id)) is None:
        needs.append("plot")
    case.needs = needs


# Health


@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "gemini": settings.gemini_enabled, "version": VERSION}


# Cases


@app.post("/api/cases")
def create_case(
    request: Request,
    lat: float = Form(...),
    lon: float = Form(...),
    lang: str = Form("hi"),
    text: str | None = Form(None),
    audio: Annotated[UploadFile | None, File()] = None,
    insured: str | None = Form(None),
    crop_stage: str | None = Form(None),
) -> dict:
    if insured is not None and insured not in INSURED_VALUES:
        raise HTTPException(422, detail=f"insured must be one of {sorted(INSURED_VALUES)}")
    if crop_stage is not None and crop_stage not in CROP_STAGES:
        raise HTTPException(422, detail=f"crop_stage must be one of {sorted(CROP_STAGES)}")
    try:
        check_pin(lat, lon)
    except PlotRejected as exc:
        raise HTTPException(422, detail=exc.as_detail()) from exc
    if lang not in ("hi", "en", "te"):
        raise HTTPException(422, detail="lang must be one of hi, en, te")
    _check_form_text(text, report_parse.MAX_TEXT_CHARS, "text")
    audio_bytes = _read_audio(audio) if audio is not None else None
    limits.enforce(request, "cases", get_settings().rate_cases_per_hour)

    from app.agent import llm

    audio_failed = False
    parsed = report_parse.parse_text(text)
    if llm.available():
        llm_parsed = None
        if audio is not None:
            llm_parsed = llm.bounded(
                60, llm.parse_audio, audio_bytes, audio.content_type or "audio/webm", lang
            )
            audio_failed = llm_parsed is None
        elif text:
            llm_parsed = llm.bounded(25, llm.parse_text, text, lang)
        if llm_parsed is not None:
            # A voice note has no typed text, so the fixed rules read what Gemini heard to fill gaps.
            fallback = parsed if parsed.transcript else report_parse.parse_text(llm_parsed.transcript)
            parsed = llm.merge_parsed(llm_parsed, fallback)
    elif audio is not None:
        audio_failed = True

    needs = report_parse.needs_for(parsed.crop, parsed.event_type, parsed.event_date)
    needs.extend(_route_needs(insured, crop_stage))
    needs.append("plot")
    if audio_failed and not parsed.transcript:
        needs.insert(0, "transcript")
    with session_scope() as s:
        case = Case(
            lat=lat, lon=lon, lang=lang, transcript=parsed.transcript, crop=parsed.crop,
            event_type=parsed.event_type, event_date=parsed.event_date,
            event_time=parsed.event_time, parsed=parsed.as_dict(), needs=needs,
            insured=insured, crop_stage=crop_stage,
        )
        s.add(case)
        s.flush()
        case_id = case.id
    return {
        "case_id": case_id,
        "parsed": {
            "crop": parsed.crop, "event_type": parsed.event_type,
            "event_date": parsed.event_date.isoformat() if parsed.event_date else None,
            "event_time": parsed.event_time, "transcript": parsed.transcript,
            "confidence": parsed.confidence, "llm_used": parsed.llm_used,
            "date_note": parsed.date_note, "clarifying_question": parsed.clarifying_question,
        },
        "needs": needs,
        "questions": {n: QUESTIONS[n] for n in needs if n in QUESTIONS},
    }


class PlotBody(BaseModel):
    polygon: dict


_WARNING_TEXT = {
    "too_small_photo_evidence_advised": (
        "खेत 0.2 हेक्टेयर से छोटा है। सैटेलाइट का सबूत कम भरोसेमंद होगा, इसलिए खेत की तस्वीरें भी रखें।",
        "This plot is under 0.2 ha, too small for reliable satellite evidence. Keep photographs too.",
    ),
    "large_plot_slower_analysis": (
        "खेत 10 हेक्टेयर से बड़ा है, इसलिए जाँच में ज़्यादा समय लग सकता है।",
        "This plot is over 10 ha, so the analysis may take longer.",
    ),
}


@app.put("/api/cases/{case_id}/plot")
def put_plot(case_id: str, body: PlotBody) -> dict:
    try:
        result = validate_polygon(body.polygon)
    except PlotRejected as exc:
        raise HTTPException(422, detail=exc.as_detail()) from exc
    with session_scope() as s:
        case = _get_case(s, case_id)
        if runner.active_run_id(case_id):
            raise HTTPException(409, detail="an investigation is running; the plot cannot change")
        plot = s.scalar(select(Plot).where(Plot.case_id == case_id))
        if plot is None:
            plot = Plot(case_id=case_id)
            s.add(plot)
        plot.geometry = result.geometry
        plot.area_ha = result.area_ha
        plot.centroid_lon, plot.centroid_lat = result.centroid
        plot.crs = result.crs
        plot.warnings = result.warnings
        s.flush()
        _refresh_needs(s, case)
    return {
        "area_ha": result.area_ha,
        "warnings": [_WARNING_TEXT[w][1] for w in result.warnings],
        "warnings_hi": [_WARNING_TEXT[w][0] for w in result.warnings],
        "warning_codes": result.warnings,
    }


class CasePatch(BaseModel):
    crop: _text(64) | None = None
    event_type: _text(32) | None = None
    event_date: date | None = None
    event_time: _text(8) | None = None
    insured: _text(16) | None = None
    crop_stage: _text(32) | None = None


@app.patch("/api/cases/{case_id}")
def patch_case(case_id: str, body: CasePatch) -> dict:
    fields = body.model_fields_set
    if "event_type" in fields and body.event_type not in EVENT_TYPES:
        raise HTTPException(422, detail=f"event_type must be one of {sorted(EVENT_TYPES)}")
    if "insured" in fields and body.insured not in INSURED_VALUES:
        raise HTTPException(422, detail=f"insured must be one of {sorted(INSURED_VALUES)}")
    if "crop_stage" in fields and body.crop_stage not in CROP_STAGES:
        raise HTTPException(422, detail=f"crop_stage must be one of {sorted(CROP_STAGES)}")
    if body.event_date is not None:
        _date_error(body.event_date)
    if body.event_time is not None and not report_parse.valid_clock_time(body.event_time):
        raise HTTPException(422, detail="event_time must be HH:MM (24 hour, IST)")
    with session_scope() as s:
        case = _get_case(s, case_id)
        if "crop" in fields:
            case.crop = body.crop
        if "event_type" in fields:
            case.event_type = body.event_type
        if "event_date" in fields:
            case.event_date = body.event_date
            case.date_source = "farmer"
            case.proposed_event_date = None
        if "event_time" in fields:
            case.event_time = body.event_time
        if "insured" in fields:
            case.insured = body.insured
        if "crop_stage" in fields:
            case.crop_stage = body.crop_stage
        s.flush()
        _refresh_needs(s, case)
        s.flush()
        return _case_dict(s, case)


@app.post("/api/cases/{case_id}/investigate")
def investigate(case_id: str, request: Request) -> dict:
    with session_scope() as s:
        case = _get_case(s, case_id)
        if s.scalar(select(Plot.id).where(Plot.case_id == case_id)) is None:
            raise HTTPException(
                422,
                detail={"code": "needs_plot", "needs": ["plot"],
                        "message_hi": QUESTIONS["plot"]["hi"], "message_en": QUESTIONS["plot"]["en"],
                        "message_te": QUESTIONS["plot"]["te"]},
            )
        if case.event_date is not None:
            _date_error(case.event_date)  # a row written before this check existed
    # Asking again while a run is active starts nothing, so it costs nothing.
    if (active := runner.active_run_id(case_id)) is not None:
        return {"run_id": active, "created": False}
    limits.enforce(request, "investigations", get_settings().rate_investigations_per_hour)
    try:
        run_id, created = runner.start_run(case_id, "user")
    except runner.QueueFull as exc:
        raise limits.busy() from exc
    return {"run_id": run_id, "created": created}


def _with_live_route(evidence: dict, case: Case, lang: str) -> dict:
    """Deadline status moves with the clock, and the route with the farmer's answers. Neither is
    part of the sealed hash, so each read recomputes them from the case as it stands now."""
    from app.agent import claim_path
    from app.evidence.schema import PolicyClause
    from app.tools import policy

    path, deadlines = claim_path.for_case(case, lang)
    clauses = [PolicyClause.model_validate(c) for c in evidence.get("policy") or []]
    policy.ensure_cited(path, clauses, deadlines)
    evidence["policy"] = [c.model_dump(mode="json") for c in clauses]
    evidence["claim_path"] = path.model_dump(mode="json")
    evidence["claim_path_text"] = claim_path.text_by_language(case)
    others = [d for d in (evidence.get("deadlines") or []) if d.get("type") != "intimation_72h"]
    evidence["deadlines"] = [d.model_dump(mode="json") for d in deadlines] + others
    draw = (evidence.get("village") or {}).get("lottery")
    if draw is not None:
        draw["rule_applicability"] = claim_path.draw_applicability(path.route)
    return evidence


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, request: Request, lang: str | None = Query(None)) -> dict:
    with session_scope() as s:
        case = _get_case(s, case_id)
        # The run first and the evidence second: a run that finishes between these two reads then
        # shows as still active with its seal, which corrects itself on the next poll, and never as
        # finished without one.
        info = _case_dict(s, case)
        row = _latest_evidence(s, case_id)
        evidence = parsed = None
        if row is not None:
            evidence = _public_evidence(current_text.refresh(_with_live_route(dict(row.json), case, lang or case.lang)))
            parsed = Evidence.model_validate(evidence)
        items = s.scalars(
            select(Action).where(Action.case_id == case_id).order_by(Action.created_at)
        ).all()
        out = [_action_dict(a) for a in items]
        if evidence is not None:
            _refresh_draft(out, info, evidence, limits.web_base(request))
        # The plot the shown evidence was read on, which a later redraw does not change.
        centroid = ((evidence or {}).get("plot") or {}).get("centroid") or (info["plot"] or {}).get("centroid")
        return {
            "case": info, "evidence": evidence, "actions": out,
            "selection_note": disclosures.selection_note(centroid),
            "sealed": bool(row is not None and row.evidence_hash),
            "verdict_ready": bool(row is not None and row.verdict_level),
            "exhibits": _public_exhibits(row.exhibits) if row is not None else {},
            "corroboration": _corroboration(parsed),
            "recheck_closed": _recheck_closed(parsed, out),
            "rubric": {
                "version": rubric.RUBRIC_VERSION, "p_field": rubric.P_FIELD,
                "strong_delta": rubric.STRONG_DELTA, "moderate_delta": rubric.MODERATE_DELTA,
                "near_low": rubric.P_NEAR_LOW, "near_high": rubric.P_NEAR_HIGH,
                "near_line_decides": _near_line_decides(parsed),
            },
        }


def _public_evidence(evidence: dict) -> dict:
    """A record written before these were dropped can still hold model-written text."""
    if evidence.get("news"):
        evidence["news"] = [{k: v for k, v in item.items() if k != "snippet"} for item in evidence["news"]]
    return evidence


def _public_exhibits(exhibits: dict | None) -> dict:
    shown = {name: advisory.public(name, entry) for name, entry in (exhibits or {}).items()}
    return {
        name: {**entry, "reason": errors.public_text(entry.get("reason"), "it could not be computed; it can be retried")}
        for name, entry in shown.items()
    }


def _corroboration(ev: Evidence | None) -> dict | None:
    """Which sources the level rested on. Related reports are never among them."""
    if ev is None:
        return None
    return {"sources": rubric.corroboration(ev), "matching_alert_ids": [a.identifier for a in rubric.matching_alerts(ev)]}


def _recheck_closed(ev: Evidence | None, actions: list[dict]) -> bool:
    """This result would call for a later image, and the window for one has passed."""
    if ev is None or ev.verdict is None:
        return False
    if any(a["type"] == "recheck" and a["status"] == "open" for a in actions):
        return False
    return rubric.decide(ev).schedule_recheck and not rubric.recheck_possible(ev)


def _near_line_decides(ev: Evidence | None) -> bool:
    """Said beside the two answers. Worked out at read time, so a record sealed earlier says it too."""
    if ev is None or ev.verdict is None:
        return False
    return rubric.level_could_change(ev, ev.verdict.level)


def _refresh_draft(items: list[dict], info: dict, evidence: dict, base_url: str) -> None:
    """Route, deadline and filed status in the draft follow the current state of the case."""
    from app.evidence.schema import ClaimPath, Deadline
    from app.tools import actions as actions_tool

    draft = next((a for a in items if a["type"] == "intimation_draft"), None)
    if draft is None or not draft["payload"].get("available", True):
        return
    path = ClaimPath.model_validate(evidence["claim_path"])
    deadlines = [Deadline.model_validate(d) for d in evidence.get("deadlines") or []]
    payload = actions_tool.draft_intimation(info, evidence, path, deadlines, base_url)
    submission = next((a["payload"] for a in items if a["type"] == "submission"), None)
    payload["filed"] = bool(submission and submission.get("reference_no"))
    draft["payload"] = payload


RETRYABLE_EXHIBITS = {"sar", "history", "village", "scale_fade", "chips", "timeline"}


@app.post("/api/cases/{case_id}/exhibits/{name}/retry")
def retry_exhibit(case_id: str, name: str, request: Request) -> dict:
    if name not in RETRYABLE_EXHIBITS:
        raise HTTPException(422, detail=f"exhibit must be one of {sorted(RETRYABLE_EXHIBITS)}")
    with session_scope() as s:
        _get_case(s, case_id)
        row = _latest_evidence(s, case_id)
        if row is None or not row.evidence_hash:
            raise HTTPException(409, detail="the evidence is not sealed yet")
        status = (row.exhibits or {}).get(name, {}).get("status")
        if status not in ("failed", "not_applicable"):
            raise HTTPException(409, detail=f"exhibit {name} is {status or 'not recorded'}, so there is nothing to retry")
        if (blocker := rubric.retry_blocker(Evidence.model_validate(row.json), name)) is not None:
            raise HTTPException(409, detail={
                "code": "exhibit_inputs_missing", "reason": blocker,
                "message_hi": "यह हिस्सा दोबारा नहीं बन सकता, क्योंकि इसके लिए ज़रूरी तस्वीरें इस रिकॉर्ड में नहीं हैं।",
                "message_en": f"This cannot be run again: {blocker}.",
                "message_te": "దీన్ని మళ్ళీ నడపలేం, ఎందుకంటే దీనికి అవసరమైన చిత్రాలు ఈ రికార్డులో లేవు.",
            })
    if runner.active_run_id(case_id):
        raise HTTPException(409, detail="another run is active on this case")
    limits.enforce(request, "investigations", get_settings().rate_investigations_per_hour)
    try:
        run_id = runner.start_retry(case_id, name)
    except runner.QueueFull as exc:
        raise limits.busy() from exc
    if run_id is None:
        raise HTTPException(409, detail="another run is active on this case")
    return {"run_id": run_id, "exhibit": name, "status": "pending"}


# The live trace


def _public_event(payload: dict) -> dict:
    """A trace event as a reader may see it, whenever it was written: an older one can hold raw
    exception text or the model's own reasoning."""
    detail = {k: v for k, v in (payload.get("detail") or {}).items() if k not in ("error", "rationale")}
    return {**payload, "detail": detail, "title_en": errors.scrub(payload.get("title_en") or ""),
            "title_hi": errors.scrub(payload.get("title_hi") or "")}


def _last_event_id(value: str | None) -> int:
    """str.isdigit() also accepts characters like a superscript two, which int() then refuses."""
    if value and value.isascii() and value.isdigit() and len(value) <= 16:
        return int(value)
    return 0


def _events_after(run_id: str, after: int) -> tuple[list[dict], str | None]:
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is None:
            return [], None
        rows = s.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.seq > after)
            .order_by(RunEvent.seq)
        ).all()
        return [_public_event(r.payload) for r in rows], run.status


@app.get("/api/runs/{run_id}/stream")
async def stream_run(
    run_id: str,
    after: int = Query(0, ge=0, le=MAX_AFTER),
    last_event_id: str | None = Header(None),
) -> EventSourceResponse:
    _, status = await asyncio.to_thread(_events_after, run_id, 10**9)
    if status is None:
        raise HTTPException(404, detail="unknown run")
    after = max(after, _last_event_id(last_event_id))
    poll = get_settings().sse_poll_s

    async def generate() -> AsyncIterator[dict]:
        cursor = after
        while True:
            events, current = await asyncio.to_thread(_events_after, run_id, cursor)
            for event in events:
                cursor = event["seq"]
                yield {"id": str(event["seq"]), "data": json.dumps(event, ensure_ascii=False)}
                if event["type"] == "done":
                    return
            if not events and current not in runner.ACTIVE:
                return  # already finished and the client has everything
            await asyncio.sleep(poll)

    return EventSourceResponse(generate(), ping=15)


# Documents


_PDF_RENDERS = threading.BoundedSemaphore(2)  # each render is heavy on memory
PDF_TEXT_VERSION = 2  # raised when the fixed wording or labels change, so an older render is not reused


def _pdf_cache_path(evidence: Evidence, case: dict, exhibits: dict, lang: str, base_url: str) -> Path:
    """Everything the page prints that is not fixed by the seal: the route as it stands now, the
    deadline's status, what could not be computed, and where the QR code points."""
    state = {
        "text_version": PDF_TEXT_VERSION,
        "lang": lang, "base_url": base_url, "event_time": case.get("event_time"),
        "district": case.get("district"), "state": case.get("state"),
        "claim_path": evidence.claim_path.model_dump(mode="json") if evidence.claim_path else None,
        "deadlines": [d.model_dump(mode="json") for d in evidence.deadlines],
        "failed": sorted((k, v.get("reason") or "") for k, v in exhibits.items()
                         if v.get("status") == "failed" and k not in advisory.NAMES),
    }
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    folder = f"pdf_{evidence.evidence_hash[:16]}"
    return get_settings().artifacts_dir / evidence.case_id / folder / f"{lang}_{digest}.pdf"


def _write_atomic(path: Path, data: bytes) -> None:
    """A failed cache write costs only a re-render."""
    temporary = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(data)
        os.replace(temporary, path)
    except OSError as exc:
        log.warning("could not cache a rendered PDF: %s", exc)
        temporary.unlink(missing_ok=True)


@app.get("/api/cases/{case_id}/evidence.pdf")
def evidence_pdf(case_id: str, request: Request, lang: str = Query("hi")) -> Response:
    if lang not in ("hi", "en", "te"):
        raise HTTPException(422, detail="lang must be one of hi, en, te")
    with session_scope() as s:
        case = _get_case(s, case_id)
        row = _latest_evidence(s, case_id)
        if row is None:
            raise HTTPException(404, detail="no evidence yet; run the investigation first")
        if not row.evidence_hash:
            raise HTTPException(
                409,
                detail={
                    "code": "exhibits_pending",
                    "message_hi": "बाकी सबूत अभी बन रहे हैं। पूरा होने पर PDF तैयार होगा।",
                    "message_en": "The exhibits are still computing. The PDF is ready once they settle.",
                    "message_te": "మిగతా ఆధారాలు ఇంకా తయారవుతున్నాయి. అవి పూర్తయ్యాక PDF సిద్ధమవుతుంది.",
                    "pending": [n for n, e in (row.exhibits or {}).items()
                                if e.get("status") == "pending"],
                },
            )
        evidence = Evidence.model_validate(current_text.refresh(_with_live_route(dict(row.json), case, lang)))
        case_info = _case_dict(s, case)
        items = s.scalars(select(Action).where(Action.case_id == case_id)).all()
        actions = [_action_dict(a) for a in items]
        exhibits = row.exhibits or {}
    base_url = limits.web_base(request)
    cached = _pdf_cache_path(evidence, case_info, exhibits, lang, base_url)
    # Named by the seal: a PDF gets shared, and a case id in its name would travel with it.
    headers = {"Content-Disposition": f'inline; filename="fasalsaakshi-{evidence.evidence_hash[:12]}-{lang}.pdf"'}
    if cached.is_file():
        return FileResponse(cached, media_type="application/pdf", headers=headers)
    limits.enforce(request, "pdf", get_settings().rate_pdf_renders_per_hour)
    try:
        from app.pdf.render import build_pdf

        with _PDF_RENDERS:
            pdf = build_pdf(evidence, case_info, actions, lang, exhibits, base_url=base_url)
    except OSError as exc:  # WeasyPrint needs pango and its friends from the system
        ref = errors.report(log, "the PDF renderer is unavailable", exc)
        raise HTTPException(503, detail=f"The PDF could not be made right now (ref {ref}).") from exc
    _write_atomic(cached, pdf)
    return Response(pdf, media_type="application/pdf", headers=headers)


@app.get("/api/cases/{case_id}/summary.mp3")
def summary_audio(
    case_id: str, lang: str = Query("hi"), kind: str = Query("testimony")
) -> Response:
    """Gemini TTS returns WAV, and no MP3 encoder is shipped, so this declares audio/wav honestly."""
    if kind not in ("testimony", "summary"):
        raise HTTPException(422, detail="kind must be testimony or summary")
    if lang not in ("hi", "en", "te"):  # it goes into a file name
        raise HTTPException(422, detail="lang must be one of hi, en, te")
    from app.agent import explain

    with session_scope() as s:
        _get_case(s, case_id)
        row = _latest_evidence(s, case_id)
        if row is None:
            raise HTTPException(404, detail="no evidence yet")
        evidence = Evidence.model_validate(current_text.refresh(dict(row.json)))
    path = explain.summary_audio_path(evidence, lang, kind)
    if path is None:
        raise HTTPException(404, detail="no TTS available; use browser speech")
    return FileResponse(path, media_type="audio/wav")


# Actions and questions


class SubmissionBody(BaseModel):
    channel: _text(64) | None = None
    reference_no: _text(100) | None = None
    submitted_at: datetime | None = None


@app.post("/api/cases/{case_id}/submission")
def record_submission(case_id: str, body: SubmissionBody) -> dict:
    reference = (body.reference_no or "").strip()
    if not reference:
        raise HTTPException(
            422,
            detail={
                "code": "reference_required",
                "message_hi": "संदर्भ संख्या के बिना इसे दर्ज किया हुआ नहीं माना जा सकता।",
                "message_en": "This cannot be marked as filed without a reference number.",
            },
        )
    when = body.submitted_at or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=report_parse.IST)
    if when > datetime.now(UTC) + timedelta(minutes=5):  # a few minutes of clock difference is fine
        raise HTTPException(422, detail=_message(
            "दर्ज करने का समय आने वाले समय में नहीं हो सकता। कृपया सही तारीख़ और समय चुनें।",
            "The time you filed cannot be in the future. Please pick the right date and time.",
            "నమోదు చేసిన సమయం భవిష్యత్తులో ఉండకూడదు. దయచేసి సరైన తేదీ, సమయం ఎంచుకోండి.",
            "submitted_at_future",
        ))
    if when.date() < report_parse.EARLIEST_EVENT_DATE:
        raise HTTPException(422, detail=_message(
            "यह तारीख़ बहुत पुरानी है। कृपया सही तारीख़ और समय चुनें।",
            "That date is too far back. Please pick the right date and time.",
            "ఈ తేదీ చాలా పాతది. దయచేసి సరైన తేదీ, సమయం ఎంచుకోండి.",
            "submitted_at_too_early",
        ))
    with session_scope() as s:
        case = _get_case(s, case_id)
        s.add(
            Action(
                case_id=case_id, type="submission", status="done",
                payload={"channel": body.channel, "reference_no": reference,
                         "submitted_at": when.isoformat()},
            )
        )
        case.status = "submitted"
        s.flush()
        return _case_dict(s, case)


class AskBody(BaseModel):
    question: _text(500)
    lang: _text(8) = "hi"


@app.post("/api/cases/{case_id}/ask")
def ask(case_id: str, body: AskBody, request: Request) -> dict:
    """Answers from this case's record and the cited clauses. It reads the record and writes nothing."""
    from app.agent import claim_path, witness

    with session_scope() as s:
        case = _get_case(s, case_id)
        limits.enforce(request, "asks", get_settings().rate_asks_per_hour)
        row = _latest_evidence(s, case_id)
        evidence, next_steps = None, None
        if row is not None and row.verdict_level:
            evidence = Evidence.model_validate(current_text.refresh(_with_live_route(
                dict(row.json), case, body.lang if body.lang in ("hi", "en", "te") else case.lang)))
            next_steps = claim_path.text_by_language(case)
    return witness.ask(body.question, body.lang, evidence, next_steps)


@app.post("/api/cases/{case_id}/advisories")
def start_advisories(case_id: str, request: Request) -> dict:
    """Starts what Gemini has not yet looked at on this record: the runs do this themselves, and a
    record sealed before a key existed gets it here. A request that starts nothing costs nothing."""
    from app.agent import llm

    with session_scope() as s:
        case = _get_case(s, case_id)
        row = _latest_evidence(s, case_id)
        if row is None or not row.verdict_level:
            raise HTTPException(409, detail="there is no result to look at yet")
        evidence = Evidence.model_validate(row.json)
        run_id, exhibits = row.run_id, dict(row.exhibits or {})
        transcript, crop_stage = case.transcript, case.crop_stage
    if not llm.available():
        return {"gemini": False, "started": []}
    wanted = []
    for name in advisory.NAMES:
        entry = exhibits.get(name)
        if entry is None or entry.get("status") == "failed" or advisory.is_stale(entry):
            wanted.append(name)
    if (exhibits.get("chips") or {}).get("status", "done") != "done" and advisory.IMAGE_OPINION in wanted:
        wanted.remove(advisory.IMAGE_OPINION)
    if not wanted:
        return {"gemini": True, "started": []}
    limits.enforce(request, "advisories", get_settings().rate_advisories_per_hour)
    return {"gemini": True, "started": advisory.start(run_id, evidence, tuple(wanted), transcript, crop_stage)}


# Verification, artifacts, jobs, radar


@app.get("/api/verify/{evidence_hash}")
async def verify_hash(
    evidence_hash: str,
    request: Request,
    after: int = Query(0, ge=0, le=MAX_AFTER),
    rerun: bool = Query(False),
    last_event_id: str | None = Header(None),
) -> EventSourceResponse:
    from app import verify

    after = max(after, _last_event_id(last_event_id))
    ip = limits.client_ip(request)

    def may_start() -> None:
        """Only a new download counts: a running job or a stored check costs nothing to read."""
        if (wait := limits.retry_after("verify", ip, get_settings().rate_verify_per_hour)) is not None:
            raise limits.too_many(wait)

    prepared = await asyncio.to_thread(verify.prepare, evidence_hash, after, rerun, may_start)
    return EventSourceResponse(verify.follow(prepared, after), ping=15)


def _inside(root: Path, path: str) -> Path | None:
    """The file under root, or None. A very long name or a NUL makes the OS itself object."""
    try:
        target = (root / path).resolve()
        return target if target.is_relative_to(root) and target.is_file() else None
    except (OSError, ValueError):
        return None


@app.get("/api/artifacts/{path:path}")
def artifact(path: str) -> FileResponse:
    target = _inside(get_settings().artifacts_dir.resolve(), path)
    if target is None:
        raise HTTPException(404, detail="no such artifact")
    return FileResponse(target)


@app.post("/api/jobs/tick")
def jobs_tick(x_scheduler_token: str | None = Header(None)) -> dict:
    from app import jobs

    token = get_settings().scheduler_token
    if not token or not hmac.compare_digest((x_scheduler_token or "").encode(), token.encode()):
        # Closed when no token is set: the in-process scheduler does not need this route.
        raise HTTPException(403, detail="bad scheduler token")
    return jobs.tick()


@app.get("/api/radar")
def radar() -> dict:
    from app.tools import weather

    try:
        return weather.radar()
    except weather.WeatherUnavailable as exc:
        ref = errors.report(log, "radar: no weather source", exc)
        raise HTTPException(503, detail=_message(
            "मौसम का स्रोत अभी उपलब्ध नहीं है। थोड़ी देर बाद फिर कोशिश करें।",
            f"The weather source is not available right now (ref {ref}). Please try again shortly.",
            "వాతావరణ మూలం ఇప్పుడు అందుబాటులో లేదు. కాసేపటి తర్వాత ప్రయత్నించండి.",
            "weather_unavailable",
        )) from exc


# The built web app, with SPA fallback


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> Response:
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, detail="no such API route")
    if "\x00" in path or len(path) > 1024:
        raise HTTPException(404, detail="no such page")
    dist: Path = get_settings().web_dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return JSONResponse(
            status_code=404,
            content={"detail": "the web app is not built; API routes are under /api"},
        )
    target = _inside(dist, path) if path else None
    return FileResponse(target or index)

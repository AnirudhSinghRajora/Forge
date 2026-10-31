"""FastAPI app: every route in the build contract under /api, plus the built web app at /."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, get_args

from fastapi import FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.agent import parse as report_parse
from app.agent import runner
from app.agent.plot import PlotRejected, check_pin, validate_polygon
from app.config import VERSION, get_settings
from app.db import Action, Case, EvidenceRow, Plot, Run, RunEvent, init_db, session_scope
from app.evidence.schema import EventType, Evidence

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

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
    closed = runner.recover_interrupted()
    if closed:
        log.warning("closed %d runs interrupted by the last restart", closed)
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


app = FastAPI(title="FasalSaakshi", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error", exc_info=exc)
    return JSONResponse(
        status_code=500, content={"detail": f"internal error: {type(exc).__name__}: {exc}"}
    )


# Helpers


def _get_case(s, case_id: str) -> Case:
    case = s.get(Case, case_id)
    if case is None:
        raise HTTPException(404, detail=f"unknown case {case_id}")
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
            "error": latest.error,
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
    """The newest run with a verdict, else the newest sealed, else whatever exists. A re-run that
    has no verdict yet never blanks the earlier result."""
    rows = s.scalars(
        select(EvidenceRow).where(EvidenceRow.case_id == case_id)
        .order_by(EvidenceRow.created_at.desc())
    ).all()
    if rows and (rows[0].verdict_level or rows[0].evidence_hash):
        return rows[0]  # the verdict of the newest run shows at once, while its exhibits fill in
    return next((r for r in rows if r.evidence_hash), rows[0] if rows else None)


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

    from app.agent import llm

    audio_failed = False
    parsed = report_parse.parse_text(text)
    if llm.available():
        llm_parsed = None
        if audio is not None:
            llm_parsed = llm.bounded(
                60, llm.parse_audio, audio.file.read(), audio.content_type or "audio/webm", lang
            )
            audio_failed = llm_parsed is None
        elif text:
            llm_parsed = llm.bounded(25, llm.parse_text, text, lang)
        if llm_parsed is not None:
            parsed = llm.merge_parsed(llm_parsed, parsed)
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
            "date_note": parsed.date_note,
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
    crop: str | None = None
    event_type: str | None = None
    event_date: date | None = None
    event_time: str | None = None
    insured: str | None = None
    crop_stage: str | None = None


@app.patch("/api/cases/{case_id}")
def patch_case(case_id: str, body: CasePatch) -> dict:
    fields = body.model_fields_set
    if "event_type" in fields and body.event_type not in EVENT_TYPES:
        raise HTTPException(422, detail=f"event_type must be one of {sorted(EVENT_TYPES)}")
    if "insured" in fields and body.insured not in INSURED_VALUES:
        raise HTTPException(422, detail=f"insured must be one of {sorted(INSURED_VALUES)}")
    if "crop_stage" in fields and body.crop_stage not in CROP_STAGES:
        raise HTTPException(422, detail=f"crop_stage must be one of {sorted(CROP_STAGES)}")
    if body.event_date is not None and body.event_date > report_parse.today_ist():
        raise HTTPException(422, detail="event_date cannot be in the future")
    if body.event_time is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", body.event_time):
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
def investigate(case_id: str) -> dict:
    with session_scope() as s:
        _get_case(s, case_id)
        if s.scalar(select(Plot.id).where(Plot.case_id == case_id)) is None:
            raise HTTPException(
                422,
                detail={"code": "needs_plot", "needs": ["plot"],
                        "message_hi": QUESTIONS["plot"]["hi"], "message_en": QUESTIONS["plot"]["en"]},
            )
    run_id, created = runner.start_run(case_id, "user")
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
def get_case(case_id: str, lang: str | None = Query(None)) -> dict:
    with session_scope() as s:
        case = _get_case(s, case_id)
        row = _latest_evidence(s, case_id)
        evidence = None
        if row is not None:
            evidence = _with_live_route(dict(row.json), case, lang or case.lang)
        items = s.scalars(
            select(Action).where(Action.case_id == case_id).order_by(Action.created_at)
        ).all()
        info = _case_dict(s, case)
        out = [_action_dict(a) for a in items]
        if evidence is not None:
            _refresh_draft(out, info, evidence)
        return {
            "case": info, "evidence": evidence, "actions": out,
            "sealed": bool(row is not None and row.evidence_hash),
            "verdict_ready": bool(row is not None and row.verdict_level),
            "exhibits": (row.exhibits or {}) if row is not None else {},
        }


def _refresh_draft(items: list[dict], info: dict, evidence: dict) -> None:
    """Route, deadline and filed status in the draft follow the current state of the case."""
    from app.evidence.schema import ClaimPath, Deadline
    from app.tools import actions as actions_tool

    draft = next((a for a in items if a["type"] == "intimation_draft"), None)
    if draft is None or not draft["payload"].get("available", True):
        return
    path = ClaimPath.model_validate(evidence["claim_path"])
    deadlines = [Deadline.model_validate(d) for d in evidence.get("deadlines") or []]
    payload = actions_tool.draft_intimation(info, evidence, path, deadlines)
    submission = next((a["payload"] for a in items if a["type"] == "submission"), None)
    payload["filed"] = bool(submission and submission.get("reference_no"))
    draft["payload"] = payload


RETRYABLE_EXHIBITS = {"sar", "history", "village", "scale_fade", "chips", "timeline"}


@app.post("/api/cases/{case_id}/exhibits/{name}/retry")
def retry_exhibit(case_id: str, name: str) -> dict:
    if name not in RETRYABLE_EXHIBITS:
        raise HTTPException(422, detail=f"exhibit must be one of {sorted(RETRYABLE_EXHIBITS)}")
    with session_scope() as s:
        _get_case(s, case_id)
        row = _latest_evidence(s, case_id)
        if row is None or not row.evidence_hash:
            raise HTTPException(409, detail="the evidence is not sealed yet")
        status = (row.exhibits or {}).get(name, {}).get("status")
        if status not in ("failed", "not_applicable"):
            raise HTTPException(409, detail=f"exhibit {name} is {status}, so there is nothing to retry")
    run_id = runner.start_retry(case_id, name)
    if run_id is None:
        raise HTTPException(409, detail="another run is active on this case")
    return {"run_id": run_id, "exhibit": name, "status": "pending"}


# The live trace


def _events_after(run_id: str, after: int) -> tuple[list[dict], str | None]:
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is None:
            return [], None
        rows = s.scalars(
            select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.seq > after)
            .order_by(RunEvent.seq)
        ).all()
        return [r.payload for r in rows], run.status


@app.get("/api/runs/{run_id}/stream")
async def stream_run(
    run_id: str,
    after: int = Query(0, ge=0),
    last_event_id: str | None = Header(None),
) -> EventSourceResponse:
    _, status = await asyncio.to_thread(_events_after, run_id, 10**9)
    if status is None:
        raise HTTPException(404, detail=f"unknown run {run_id}")
    if last_event_id and last_event_id.isdigit():
        after = max(after, int(last_event_id))
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


@app.get("/api/cases/{case_id}/evidence.pdf")
def evidence_pdf(case_id: str, lang: str = Query("hi")) -> Response:
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
                    "pending": [n for n, e in (row.exhibits or {}).items()
                                if e.get("status") == "pending"],
                },
            )
        evidence = Evidence.model_validate(_with_live_route(dict(row.json), case, lang))
        case_info = _case_dict(s, case)
        items = s.scalars(select(Action).where(Action.case_id == case_id)).all()
        actions = [_action_dict(a) for a in items]
        exhibits = row.exhibits or {}
    try:
        from app.pdf.render import build_pdf

        pdf = build_pdf(evidence, case_info, actions, lang, exhibits)
    except OSError as exc:  # WeasyPrint needs pango and its friends from the system
        raise HTTPException(503, detail=f"PDF renderer unavailable: {exc}") from exc
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="fasalsaakshi-{case_id[:8]}-{lang}.pdf"'},
    )


@app.get("/api/cases/{case_id}/summary.mp3")
def summary_audio(
    case_id: str, lang: str = Query("hi"), kind: str = Query("testimony")
) -> Response:
    """Gemini TTS returns WAV, and no MP3 encoder is shipped, so this declares audio/wav honestly."""
    if kind not in ("testimony", "summary"):
        raise HTTPException(422, detail="kind must be testimony or summary")
    from app.agent import explain

    with session_scope() as s:
        _get_case(s, case_id)
        row = _latest_evidence(s, case_id)
        if row is None:
            raise HTTPException(404, detail="no evidence yet")
        evidence = Evidence.model_validate(row.json)
    path = explain.summary_audio_path(evidence, lang, kind)
    if path is None:
        raise HTTPException(404, detail="no TTS available; use browser speech")
    return FileResponse(path, media_type="audio/wav")


# Actions and questions


class SubmissionBody(BaseModel):
    channel: str | None = None
    reference_no: str | None = None
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
    question: str
    lang: str = "hi"


@app.post("/api/cases/{case_id}/ask")
def ask(case_id: str, body: AskBody) -> dict:
    from app.tools import policy

    with session_scope() as s:
        _get_case(s, case_id)
    return policy.ask(body.question, body.lang)


# Verification, artifacts, jobs, radar


@app.get("/api/verify/{evidence_hash}")
async def verify_hash(evidence_hash: str) -> EventSourceResponse:
    from app import verify

    return EventSourceResponse(verify.stream(evidence_hash), ping=15)


@app.get("/api/artifacts/{path:path}")
def artifact(path: str) -> FileResponse:
    root = get_settings().artifacts_dir.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise HTTPException(404, detail="no such artifact")
    return FileResponse(target)


@app.post("/api/jobs/tick")
def jobs_tick(x_scheduler_token: str | None = Header(None)) -> dict:
    from app import jobs

    token = get_settings().scheduler_token
    if token and x_scheduler_token != token:
        raise HTTPException(403, detail="bad scheduler token")
    return jobs.tick()


@app.get("/api/radar")
def radar() -> dict:
    from app.tools import weather

    try:
        return weather.radar()
    except weather.WeatherUnavailable as exc:
        raise HTTPException(503, detail=f"weather source unavailable: {exc}") from exc


# The built web app, with SPA fallback


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str) -> Response:
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, detail=f"no such API route: /{path}")
    dist: Path = get_settings().web_dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return JSONResponse(
            status_code=404,
            content={"detail": "the web app is not built; API routes are under /api"},
        )
    target = (dist / path).resolve()
    if path and target.is_relative_to(dist) and target.is_file():
        return FileResponse(target)
    return FileResponse(index)

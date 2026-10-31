"""Gemini wrappers. Every function is optional and failure-tolerant: it returns None on no key, on
error and on timeout, and the caller always has a deterministic path.

The current docs (ai.google.dev, checked 31 Oct 2026) describe the Interactions API as the
recommended surface and generateContent as legacy but fully supported. Each call tries Interactions
first and falls back to generate_content, so one surface failing does not lose the capability.

Test once a key exists: `uv run python -m app.agent.llm --selftest`
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import sys
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import date
from typing import TypeVar

from pydantic import BaseModel

from app import errors
from app.agent.parse import MAX_TEXT_CHARS, ParsedReport, event_date_problem, today_ist, valid_clock_time
from app.config import get_settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

TTS_VOICE = "Kore"
MAX_CROP_CHARS = 64  # the column's width
LANG_NAMES = {"hi": "Hindi", "en": "English", "te": "Telugu"}
_client_lock = threading.Lock()
_client = None
_key_in_use: str | None = None
last_errors: dict[str, str] = {}


def available() -> bool:
    return get_settings().gemini_enabled


_BOUNDED = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm")


def bounded(seconds: float, fn, *args, **kwargs):
    """Calls fn with a hard wall-clock limit and returns None past it, or on any failure. A hung LLM
    must never hold up a verdict, since the deterministic path has already been built."""
    future = _BOUNDED.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=seconds)
    except FutureTimeout:
        log.warning("gemini call to %s exceeded %.0f s", getattr(fn, "__name__", "?"), seconds)
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini call to %s failed: %s", getattr(fn, "__name__", "?"), exc)
    return None


def client():
    """The SDK client, or None without a key. Imported lazily so no-key startup never touches it."""
    global _client, _key_in_use
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    with _client_lock:
        if _client is None or _key_in_use != settings.gemini_api_key:
            from google import genai
            from google.genai import types

            _client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(timeout=int(settings.gemini_timeout_s * 1000)),
            )
            _key_in_use = settings.gemini_api_key
    return _client


def _note(capability: str, surface: str, exc: Exception) -> None:
    message = f"{surface}: {type(exc).__name__}: {errors.scrub(exc)[:300]}"
    last_errors[capability] = message
    log.warning("gemini %s failed on %s", capability, message)


def _text_part(text: str) -> dict:
    return {"type": "text", "text": text}


def _legacy_parts(parts: list[dict]) -> list:
    from google.genai import types

    out = []
    for part in parts:
        if part["type"] == "text":
            out.append(types.Part.from_text(text=part["text"]))
        else:
            out.append(types.Part.from_bytes(
                data=base64.b64decode(part["data"]), mime_type=part["mime_type"]
            ))
    return out


def _structured[T: BaseModel](capability: str, model: str, parts: list[dict], schema: type[T]) -> T | None:
    gem = client()
    if gem is None:
        return None
    timeout = get_settings().gemini_timeout_s
    try:
        result = gem.interactions.create(
            model=model,
            input=parts,
            store=False,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": schema.model_json_schema(),
            },
            timeout=timeout,
        )
        return schema.model_validate_json(result.output_text or "")
    except Exception as exc:  # the SDK and pydantic raise many types; every one means "fall back"  # noqa: BLE001
        _note(capability, "interactions", exc)
    try:
        from google.genai import types

        response = gem.models.generate_content(
            model=model,
            contents=_legacy_parts(parts),
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=schema
            ),
        )
        return schema.model_validate_json(response.text or "")
    except Exception as exc:  # noqa: BLE001
        _note(capability, "generate_content", exc)
    return None


def _plain_text(capability: str, model: str, parts: list[dict]) -> str | None:
    gem = client()
    if gem is None:
        return None
    timeout = get_settings().gemini_timeout_s
    try:
        result = gem.interactions.create(model=model, input=parts, store=False, timeout=timeout)
        if result.output_text:
            return result.output_text.strip()
    except Exception as exc:  # noqa: BLE001
        _note(capability, "interactions", exc)
    try:
        response = gem.models.generate_content(model=model, contents=_legacy_parts(parts))
        return (response.text or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        _note(capability, "generate_content", exc)
    return None


# Parsing


class _ReportSchema(BaseModel):
    transcript: str
    crop: str | None = None
    event_type: str = "unknown"
    event_date: str | None = None
    event_time: str | None = None
    confidence: float = 0.0


def _report_prompt(lang: str, today: date) -> str:
    return (
        "You parse an Indian farmer's crop-loss report, which may be in Hindi, Haryanvi, Punjabi, "
        f"Telugu, English or a mix. The app language is {LANG_NAMES.get(lang, lang)}. Today is "
        f"{today.isoformat()} (IST). Return JSON. Rules: transcript = the words as spoken, in their "
        "original script. crop = lowercase English name (paddy, cotton, wheat, ...), null if not "
        "said. event_type = one of hail, unseasonal_rain, flood, cyclone, wind, pest, drought, "
        "other, unknown. event_date = YYYY-MM-DD only if stated or clearly implied (kal = "
        "yesterday, parson = two days ago); otherwise null. event_time = HH:MM (24 h) only if a "
        "clock time was stated; otherwise null. confidence = 0 to 1, how clearly the report states "
        "these. Never guess a value that was not said."
    )


def _to_report(raw: _ReportSchema) -> ParsedReport:
    event_date = None
    if raw.event_date:
        try:
            event_date = date.fromisoformat(raw.event_date)
        except ValueError:
            event_date = None
    if event_date and event_date_problem(event_date):
        event_date = None
    event_time = raw.event_time if valid_clock_time(raw.event_time) else None
    crop = (raw.crop or "").strip()[:MAX_CROP_CHARS] or None
    event_type = raw.event_type
    if event_type not in {"hail", "unseasonal_rain", "flood", "cyclone", "wind", "pest", "drought",
                          "other", "unknown"}:
        event_type = "unknown"
    return ParsedReport(
        crop=crop, event_type=event_type, event_date=event_date, event_time=event_time,
        transcript=(raw.transcript or "")[:MAX_TEXT_CHARS] or None,
        confidence=round(max(0.0, min(1.0, raw.confidence)), 2), llm_used=True,
    )


def parse_audio(audio: bytes, mime_type: str, lang: str = "hi") -> ParsedReport | None:
    if not audio or len(audio) > 18_000_000:  # the inline request limit is 20 MB in total
        return None
    mime = mime_type.split(";")[0].strip() or "audio/webm"
    parts = [
        _text_part(_report_prompt(lang, today_ist())),
        {"type": "audio", "data": base64.b64encode(audio).decode(), "mime_type": mime},
    ]
    raw = _structured("parse_audio", get_settings().gemini_model_flash, parts, _ReportSchema)
    return _to_report(raw) if raw else None


def parse_text(text: str, lang: str = "hi") -> ParsedReport | None:
    parts = [_text_part(_report_prompt(lang, today_ist())), _text_part(f"Report: {text}")]
    raw = _structured("parse_text", get_settings().gemini_model_flash, parts, _ReportSchema)
    if raw is None:
        return None
    report = _to_report(raw)
    report.transcript = text
    return report


def merge_parsed(primary: ParsedReport, fallback: ParsedReport) -> ParsedReport:
    """Gemini wins when it found a value; deterministic extraction fills what it left empty."""
    primary.crop = primary.crop or fallback.crop
    if primary.event_type == "unknown":
        primary.event_type = fallback.event_type
    primary.event_date = primary.event_date or fallback.event_date
    primary.event_time = primary.event_time or fallback.event_time
    primary.transcript = primary.transcript or fallback.transcript
    return primary


# Planning


@dataclass
class PlanChoice:
    name: str
    args: dict
    rationale: str


def plan(context: str, options: list[dict]) -> PlanChoice | None:
    """Function calling restricted to `options`. The model chooses; the graph's guards can veto."""
    gem = client()
    if gem is None or not options:
        return None
    settings = get_settings()
    names = [o["name"] for o in options]
    prompt = (
        "You are the planning step of a crop-loss investigation for an Indian farmer. Choose the "
        "next step by calling exactly one function, and put your reasoning in `rationale`. Use only "
        f"the facts given here.\n\n{context}"
    )
    try:
        tools = [{"type": "function", **o} for o in options]
        result = gem.interactions.create(
            model=settings.gemini_model_pro,
            input=prompt,
            store=False,
            tools=tools,
            generation_config={"tool_choice": {"allowed_tools": {"mode": "any", "tools": names}}},
            timeout=settings.gemini_timeout_s,
        )
        for step in result.steps or []:
            if step.type == "function_call" and step.name in names:
                args = dict(step.arguments or {})
                return PlanChoice(step.name, args, str(args.pop("rationale", "")))
    except Exception as exc:  # noqa: BLE001
        _note("plan", "interactions", exc)
    try:
        from google.genai import types

        response = gem.models.generate_content(
            model=settings.gemini_model_pro,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(function_declarations=[
                    types.FunctionDeclaration(
                        name=o["name"], description=o["description"],
                        parameters_json_schema=o["parameters"],
                    ) for o in options
                ])],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                    mode="ANY", allowed_function_names=names,
                )),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        for call in response.function_calls or []:
            if call.name in names:
                args = dict(call.args or {})
                return PlanChoice(call.name, args, str(args.pop("rationale", "")))
    except Exception as exc:  # noqa: BLE001
        _note("plan", "generate_content", exc)
    return None


# Narrative. Callers must pass all of this through agent/validate.py.


def narrate(digest: dict, lang: str) -> str | None:
    prompt = (
        f"Write a short explanation in plain, respectful {LANG_NAMES.get(lang, lang)} for a farmer "
        "about the satellite evidence on their field, in 4 to 6 sentences. Facts are in the JSON "
        "below and nothing else may be used. Rules: quote numbers only as they appear in the JSON. "
        "Say 'consistent with', never promise a payment or a claim outcome, and never mention "
        "rupees. Weather is 'model-indicated', and no weather signal does not mean no storm. Say "
        "plainly what the evidence cannot show. End with what the farmer should do next.\n\n"
        + json.dumps(digest, ensure_ascii=False, default=str)
    )
    return _plain_text(f"narrate_{lang}", get_settings().gemini_model_pro, [_text_part(prompt)])


class _Rephrased(BaseModel):
    id: str
    challenge_hi: str
    challenge_en: str


class _RephrasedList(BaseModel):
    items: list[_Rephrased]


def rephrase_challenges(objections: list[dict]) -> dict[str, tuple[str, str]] | None:
    """Rewords only the surveyor's challenges in a tougher voice. Findings stay deterministic."""
    prompt = (
        "Rewrite each challenge in the voice of a blunt, sceptical insurance surveyor speaking to "
        "a farmer: one short sentence in Hindi and one in English. Keep the meaning. Add no numbers, "
        "dates or facts, and keep each id exactly.\n\n"
        + json.dumps(objections, ensure_ascii=False)
    )
    raw = _structured("rephrase", get_settings().gemini_model_flash, [_text_part(prompt)],
                      _RephrasedList)
    if raw is None:
        return None
    return {i.id: (i.challenge_hi, i.challenge_en) for i in raw.items}


def translate(text: str, target_lang: str) -> str | None:
    prompt = (
        f"Translate into natural, simple {LANG_NAMES.get(target_lang, target_lang)} that a farmer "
        "would use. Keep every number exactly as written, and add nothing. Return only the "
        f"translation.\n\n{text}"
    )
    return _plain_text(f"translate_{target_lang}", get_settings().gemini_model_flash,
                       [_text_part(prompt)])


class _ClauseAnswer(BaseModel):
    answer: str
    cited_clause_ids: list[str]


def answer_from_clauses(question: str, clauses: list[dict], lang: str) -> _ClauseAnswer | None:
    context = "\n\n".join(f"[{c['clause_id']}] {c['text']}" for c in clauses)
    prompt = (
        f"Answer the farmer's question in simple {LANG_NAMES.get(lang, lang)} using ONLY the clauses "
        "below. If they do not answer it, set cited_clause_ids to an empty list and say that it is "
        "not covered. Do not promise any outcome. Quote numbers only as they appear in the "
        f"clauses.\n\nClauses:\n{context}\n\nQuestion: {question}"
    )
    return _structured("policy_answer", get_settings().gemini_model_flash, [_text_part(prompt)],
                       _ClauseAnswer)


# Audio out


def _pcm_to_wav(pcm: bytes, rate: int = 24_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


def tts(text: str, lang: str = "hi") -> bytes | None:
    """WAV bytes (24 kHz mono 16-bit). The model detects the language from the text's script."""
    gem = client()
    if gem is None or not text:
        return None
    settings = get_settings()
    capability = f"tts_{lang}"
    try:
        result = gem.interactions.create(
            model=settings.gemini_model_tts,
            input=[{
                "type": "user_input",
                "content": [{
                    "type": "text",
                    "text": text,
                    "annotations": [{"type": "speech_metadata",
                                     "style": "calm, clear and respectful, speaking to a farmer"}],
                }],
            }],
            store=False,
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": TTS_VOICE}]},
            timeout=max(settings.gemini_timeout_s, 60.0),
        )
        data = base64.b64decode(result.output_audio.data)
        if data:
            return data if data[:4] == b"RIFF" else _pcm_to_wav(data)
    except Exception as exc:  # noqa: BLE001
        _note(capability, "interactions", exc)
    try:
        from google.genai import types

        response = gem.models.generate_content(
            model=settings.gemini_model_tts,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=TTS_VOICE)
                )),
            ),
        )
        pcm = response.candidates[0].content.parts[0].inline_data.data
        return pcm if pcm[:4] == b"RIFF" else _pcm_to_wav(pcm)
    except Exception as exc:  # noqa: BLE001
        _note(capability, "generate_content", exc)
    return None


# Search grounding


def grounded_sources(query: str) -> list[dict] | None:
    """Only URLs the API attached as grounding citations. None means the call failed."""
    gem = client()
    if gem is None:
        return None
    settings = get_settings()
    try:
        result = gem.interactions.create(
            model=settings.gemini_model_flash,
            input=query,
            store=False,
            tools=[{"type": "google_search"}],
            timeout=settings.gemini_timeout_s,
        )
        found: dict[str, dict] = {}
        for step in result.steps or []:
            if step.type != "model_output":
                continue
            for block in step.content or []:
                if getattr(block, "type", None) != "text":
                    continue
                for ann in block.annotations or []:
                    if ann.type == "url_citation" and ann.url:
                        found.setdefault(ann.url, {"url": ann.url, "title": ann.title or ann.url})
        if found:
            return list(found.values())
    except Exception as exc:  # noqa: BLE001
        _note("search", "interactions", exc)
    try:
        from google.genai import types

        response = gem.models.generate_content(
            model=settings.gemini_model_flash,
            contents=query,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        metadata = response.candidates[0].grounding_metadata
        out = []
        for chunk in (metadata.grounding_chunks or []) if metadata else []:
            if chunk.web and chunk.web.uri:
                out.append({"url": chunk.web.uri, "title": chunk.web.title or chunk.web.uri})
        return out
    except Exception as exc:  # noqa: BLE001
        _note("search", "generate_content", exc)
    return None


# Embeddings


def embed(texts: list[str], *, is_query: bool, titles: list[str] | None = None) -> list | None:
    """gemini-embedding-2 takes no task_type; per the docs the task goes in as a text prefix."""
    gem = client()
    if gem is None or not texts:
        return None
    settings = get_settings()
    if is_query:
        contents = [f"task: search result | query: {t}" for t in texts]
    else:
        heads = titles or [""] * len(texts)
        contents = [f"title: {h} | text: {t}" for h, t in zip(heads, texts, strict=True)]
    try:
        vectors = []
        for start in range(0, len(contents), 64):
            response = gem.models.embed_content(
                model=settings.gemini_model_embed, contents=contents[start:start + 64]
            )
            vectors.extend(e.values for e in response.embeddings)
        return vectors
    except Exception as exc:  # noqa: BLE001
        _note("embed", "embed_content", exc)
    return None


# Self-test


def selftest() -> int:
    """Calls every capability against the live API and prints PASS or FAIL. No key means FAIL."""
    if not available():
        print("FAIL no GEMINI_API_KEY in the environment; the app runs on its no-key path")
        return 1
    settings = get_settings()
    print(f"models: pro={settings.gemini_model_pro} flash={settings.gemini_model_flash} "
          f"tts={settings.gemini_model_tts} embed={settings.gemini_model_embed}")
    results: dict[str, tuple[bool, str]] = {}

    def check(name, fn):
        last_errors.clear()
        try:
            ok, info = fn()
        except Exception as exc:  # noqa: BLE001
            ok, info = False, f"{type(exc).__name__}: {exc}"
        fell_back = "; fell back from " + "; ".join(last_errors.values()) if last_errors and ok else ""
        results[name] = (ok, info + fell_back)
        print(f"{'PASS' if ok else 'FAIL'} {name}: {info}{fell_back}"
              + ("" if ok else f" | errors: {dict(last_errors)}"), flush=True)

    def _parse():
        r = parse_text("कल शाम ओले गिरे, कपास की फ़सल खराब हो गई", "hi")
        return bool(r and r.event_type == "hail" and r.crop == "cotton" and r.event_date), str(
            r.as_dict() if r else None)

    def _plan():
        options = [
            {"name": "search_optical", "description": "Search optical imagery.",
             "parameters": {"type": "object", "properties": {"rationale": {"type": "string"}},
                            "required": ["rationale"]}},
            {"name": "sar_first", "description": "Use radar first.",
             "parameters": {"type": "object", "properties": {"rationale": {"type": "string"}},
                            "required": ["rationale"]}},
        ]
        r = plan("A cyclone hit 2 days ago, with heavy cloud forecast.", options)
        return bool(r and r.name in ("search_optical", "sar_first")), str(r)

    def _narrate():
        r = narrate({"verdict": "weak", "plot_delta_ndvi": -0.04, "note": "no visible change"}, "hi")
        return bool(r), (r or "")[:90]

    def _translate():
        r = translate("Your field shows a change of 0.23.", "te")
        return bool(r and "0.23" in r.translate(str.maketrans("౦౧౨౩౪౫౬౭౮౯", "0123456789"))), (r or "")[:90]

    audio_holder: dict = {}

    def _tts(lang, text):
        def inner():
            r = tts(text, lang)
            if r:
                audio_holder[lang] = r
            return bool(r and r[:4] == b"RIFF"), f"{len(r) if r else 0} bytes of WAV"
        return inner

    def _audio():
        if "hi" not in audio_holder:
            return False, "skipped: no Hindi TTS audio to feed back"
        r = parse_audio(audio_holder["hi"], "audio/wav", "hi")
        return bool(r and r.transcript), str(r.as_dict() if r else None)[:120]

    def _search():
        r = grounded_sources("Cyclone crop damage Andhra Pradesh October 2026 news")
        return bool(r), f"{len(r or [])} grounded urls; first: {(r or [{}])[0].get('url')}"

    def _embed():
        r = embed(["hail damage"], is_query=True)
        return bool(r and r[0]), f"dim {len(r[0]) if r else 0}"

    check("parse_text", _parse)
    check("plan (function calling)", _plan)
    check("narrate", _narrate)
    check("translate (te)", _translate)
    check("tts hi-IN", _tts("hi", "नमस्ते किसान भाई, कल ओले गिरे और कपास की फ़सल खराब हुई।"))
    check("tts te-IN", _tts("te", "నమస్కారం రైతు సోదరా, మీ పొలం ఆధారాలు సిద్ధంగా ఉన్నాయి."))
    check("parse_audio (round trip of the TTS output)", _audio)
    check("search grounding", _search)
    check("embeddings", _embed)
    failed = [k for k, (ok, _) in results.items() if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed" + (
        f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    if parser.parse_args().selftest:
        logging.basicConfig(level=logging.ERROR)
        sys.exit(selftest())

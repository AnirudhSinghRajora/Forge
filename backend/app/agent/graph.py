"""The investigation graph, as in the build contract, with real conditional edges.

parse -> resolve_plot -> gather_context -> planner -> search_optical
  search_optical: good pre and post -> optical_compare (radar corroborates in parallel)
                  post missing, cloudy or corrupt -> sensor_switch -> sar_compare
-> history -> cross_examine: objection needs more data and budget remains -> search_optical
                             done -> verdict -> policy -> village -> act -> explain -> seal

Every node runs behind a guard, so a failure leaves partial evidence and an honest verdict rather
than a crash. Deterministic code always yields a valid path; the optional LLM planner only chooses
among allowed options, and code-level guards can veto it.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select

from app.agent import claim_path, cross_exam, explain, llm, rubric, testimony, validate
from app.agent.cross_exam import date_en, date_hi, signed
from app.agent.parse import today_ist
from app.agent.trace import Tracer
from app.config import get_settings
from app.db import Action, Case, EvidenceRow, Plot, session_scope, utcnow
from app.evidence.schema import (
    Deadline,
    EventInfo,
    Evidence,
    OpticalEvidence,
    PlotInfo,
    Provenance,
    ReplayCore,
    SceneQA,
)
from app.tools import actions, alerts, news, policy, weather

log = logging.getLogger(__name__)

PRE_WINDOW_DAYS = 25
POST_WINDOW_DAYS = 20
MAX_POST_WINDOW_DAYS = 30
MAX_QA_PER_SEARCH = 6
QA_PREFETCH = 2
PRE_WALK_S = 45  # one search step gets a bounded share of the budget, whatever the scenes do
QA_WALK_S = 70
MAX_LOOPS = 2
SENTINEL2_REVISIT_DAYS = 5
SAME_FIELD_M = 50
PC = "Microsoft Planetary Computer"

_TIMEOUTS_S = {
    "weather": 25, "alerts": 12, "news": 30, "search_optical": 25, "qa_scene": 45,
    "optical_compare": 70, "search_sar": 25, "sar_compare": 70, "history": 75, "timeline": 150,
    "render_chips": 80, "village_witness": 80, "scale_fade": 80,
}
_CORE_TOOLS = {"optical_compare", "sar_compare"}
MAX_CORE_TIMEOUT_S = 130
# The verdict always lands inside the soft budget. Documentation after it (the village step and the
# chips) may run past it, up to this, because a sealed record is worth a slower finish.
DOCUMENTATION_GRACE_S = 75
_TOOLS = ThreadPoolExecutor(max_workers=32, thread_name_prefix="tool")
_QA_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="qa")


_TOOL_HI = {
    "weather": "मौसम का डेटा", "alerts": "सरकारी चेतावनियों की जाँच", "news": "ख़बरों की खोज", "locate": "ज़िले की पहचान",
    "search_optical": "सैटेलाइट तस्वीरों की खोज", "qa_scene": "तस्वीर की जाँच", "optical_compare": "तस्वीरों की तुलना",
    "search_sar": "रडार की खोज", "sar_compare": "रडार की तुलना", "history": "पिछले वर्षों से तुलना",
    "timeline": "सैटेलाइट दर्शनों की सूची", "render_chips": "तस्वीरें बनाना", "village_witness": "दस खेतों का ड्रॉ",
    "scale_fade": "बड़े खानों वाला चित्र",
}


def _reasons_hi(reasons: list[str]) -> str:
    """Why a scene failed, in plain Hindi. The raw reasons stay in the event's detail."""
    codes = {r[:2] for r in reasons}
    parts = []
    if "Q1" in codes:
        parts.append("तस्वीर के कुछ बैंड गायब या ख़राब हैं")
    if codes & {"Q3", "Q4"}:
        parts.append("इसके आँकड़े भौतिक रूप से संभव नहीं, यानी सेंसर का डेटा ख़राब है")
    if "Q2" in codes:
        parts.append("खेत बादल या छाया से ढका है")
    if "Q5" in codes:
        parts.append("पूरे इलाक़े की हरियाली अचानक बदली दिखती है")
    return "; ".join(parts) or "यह जाँच में पास नहीं हुई"


def _reasons_en(reasons: list[str]) -> str:
    return "; ".join(re.sub(r"^Q\d: ", "", r) for r in reasons)


class ToolFailed(Exception):
    """A tool timed out or failed. The message is safe to show in a trace."""


class BudgetExhausted(ToolFailed):
    pass


class ToolTimedOut(ToolFailed):
    pass


def _geo():
    from app.tools import geo

    return geo


def canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def evidence_hash(core: ReplayCore) -> str:
    return hashlib.sha256(canonical_json(core.model_dump(mode="json")).encode()).hexdigest()


def make_seed(polygon: dict, event_date: date) -> int:
    digest = hashlib.sha256(f"{canonical_json(polygon)}|{event_date}".encode()).hexdigest()
    return int(digest[:8], 16) % (2**31)


@dataclass
class Ctx:
    """Everything a node needs that does not belong in graph state."""
    run_id: str
    case_id: str
    tracer: Tracer
    budget_calls: int
    budget_s: float
    started: float = field(default_factory=time.monotonic)
    calls: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)
    timeline_future: Any = None
    sar_future: Any = None
    archive_failed: bool = False  # a satellite search itself failed, as opposed to finding nothing

    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def seconds_left(self) -> float:
        return self.budget_s - self.elapsed()

    def calls_left(self) -> int:
        return self.budget_calls - self.calls

    def emit(self, type_: str, node: str, hi: str, en: str, **detail) -> None:
        detail.setdefault("budget", {"calls_used": self.calls, "calls_max": self.budget_calls,
                                     "elapsed_s": round(self.elapsed(), 1)})
        self.tracer.emit(type_, node, hi, en, **detail)

    def call(
        self, node: str, tool: str, fn: Callable[[], Any], hi: str, en: str,
        summarize: Callable[[Any], dict] | None = None, counted: bool = True, **args,
    ) -> Any:
        """One tool call: budget check, tool_called, timeout, tool_result carrying real numbers."""
        with self.lock:
            if counted and self.calls >= self.budget_calls:
                exhausted = True
            else:
                exhausted = False
                if counted:
                    self.calls += 1
        if exhausted:
            self.emit("warning", node, f"टूल बजट पूरा: {_TOOL_HI.get(tool, tool)} नहीं हुआ", f"Tool budget used up: {tool} did not run",
                      tool=tool)
            raise BudgetExhausted(f"tool budget used up before {tool}")
        self.emit("tool_called", node, hi, en, tool=tool, args=args)
        timeout = _TIMEOUTS_S.get(tool, 30)
        if tool in _CORE_TOOLS:
            # A slow answer to the core question beats no answer, so these can use what is left.
            timeout = max(timeout, min(self.seconds_left() - 5, MAX_CORE_TIMEOUT_S))
        begin = time.monotonic()
        future = _TOOLS.submit(fn)
        try:
            result = future.result(timeout=timeout)
        except FutureTimeout as exc:
            # The worker keeps running until its own HTTP timeouts end it; the run moves on.
            self.emit("warning", node, f"{_TOOL_HI.get(tool, tool)} {timeout:.0f} सेकंड में पूरा नहीं हुआ",
                      f"{tool} did not finish within {timeout:.0f} s", tool=tool, timeout_s=round(timeout))
            raise ToolTimedOut(f"{tool} timed out after {timeout:.0f} s") from exc
        except Exception as exc:
            self.emit("warning", node, f"{_TOOL_HI.get(tool, tool)} नहीं हो पाया", f"{tool} failed: {exc}",
                      tool=tool, error=f"{type(exc).__name__}: {exc}")
            raise ToolFailed(f"{tool} failed: {exc}") from exc
        detail = summarize(result) if summarize else {}
        self.emit("tool_result", node, f"{hi}: पूरा", f"{en}: done", tool=tool,
                  duration_s=round(time.monotonic() - begin, 1), result=detail)
        return result


class State(TypedDict, total=False):
    evidence: Evidence | None
    case: dict
    polygon: dict
    seed: int
    stop: str | None
    farmer_date: date | None
    post_days: int
    pre_days: int
    excluded: list[str]
    pre_scene: Any
    post_scene: Any
    qa_seen: dict[str, SceneQA]
    route: str
    keep_previous: bool
    before_redate: dict | None
    accepted_pre: bool
    accepted_post: bool
    last_outcomes: dict
    loops: int
    attempted: list[str]
    sar_tried: bool
    optical_failed: bool
    sar_first: bool
    history_date: date | None
    conceded_seen: list[dict]
    llm_rephrase: dict
    weather_payload_date: date | None


def _prov(ev: Evidence, field_name: str, source: str, asset: str | None = None,
          url: str | None = None, when: datetime | None = None) -> None:
    ev.provenance.append(Provenance(
        field=field_name, source=source, asset=asset, url=url,
        retrieved_at=when or datetime.now(UTC),
    ))


def persist(ctx: Ctx, ev: Evidence | None) -> None:
    """Saved after every node, so a crash or refresh still has the evidence gathered so far."""
    if ev is None:
        return
    with session_scope() as s:
        row = s.scalar(select(EvidenceRow).where(EvidenceRow.run_id == ctx.run_id))
        if row is None:
            row = EvidenceRow(run_id=ctx.run_id, case_id=ctx.case_id, json={})
            s.add(row)
        row.json = ev.model_dump(mode="json")
        row.verdict_level = ev.verdict.level if ev.verdict else None
        row.evidence_hash = ev.evidence_hash
        row.replay_core = ev.replay.model_dump(mode="json") if ev.replay else None


def guard(name: str, ctx: Ctx, fn: Callable[[State, Ctx], dict]) -> Callable[[State], dict]:
    """Wraps a node: no exception leaves it, and the evidence is persisted after it."""

    def node(state: State) -> dict:
        update: dict = {}
        try:
            update = fn(state, ctx) or {}
        except Exception as exc:  # partial failure must yield partial evidence, never a crash
            log.exception("node %s failed in run %s", name, ctx.run_id)
            ctx.emit("error", name, "इस चरण में दिक्कत आई; आगे की जाँच जारी है।",
                     f"This step failed ({type(exc).__name__}); the investigation continues.",
                     error=f"{type(exc).__name__}: {exc}")
        try:
            persist(ctx, update.get("evidence", state.get("evidence")))
        except Exception:
            log.exception("could not persist evidence for run %s", ctx.run_id)
        return update

    return node


# parse


def n_parse(state: State, ctx: Ctx) -> dict:
    with session_scope() as s:
        case = s.get(Case, ctx.case_id)
        plot = s.scalar(select(Plot).where(Plot.case_id == ctx.case_id))
        info = {
            "id": case.id, "lat": case.lat, "lon": case.lon, "lang": case.lang,
            "crop": case.crop, "event_type": case.event_type or "unknown",
            "event_date": case.event_date, "event_time": case.event_time,
            "date_source": case.date_source, "insured": case.insured,
            "crop_stage": case.crop_stage, "transcript": case.transcript,
        }
        polygon = plot.geometry if plot else None
    ctx.emit(
        "step_started", "parse", "किसान की बात समझी जा रही है", "Reading the farmer's report",
        crop=info["crop"], event_type=info["event_type"],
        event_date=info["event_date"], event_time=info["event_time"],
    )
    update: dict = {"case": info, "polygon": polygon, "farmer_date": info["event_date"], "stop": None}
    if info["event_date"] is None:
        try:
            peak, _ = ctx.call(
                "parse", "weather",
                lambda: weather.peak_recent_date(info["lat"], info["lon"]),
                "तारीख़ नहीं बताई गई, इसलिए पिछले 14 दिनों का मौसम देखा जा रहा है",
                "No date was given, so checking the weather of the last 14 days",
                summarize=lambda r: {"peak_date": r[0]},
            )
        except ToolFailed:
            peak = None
        if peak is None:
            ctx.emit(
                "error", "parse",
                "घटना की तारीख़ के बिना जाँच नहीं हो सकती, और मौसम से भी तारीख़ नहीं मिली। कृपया तारीख़ बताएँ।",
                "The investigation needs an event date, and the weather did not suggest one. Please "
                "give the date.",
                needs=["event_date"],
            )
            update["stop"] = "needs_input"
            return update
        info["event_date"] = peak
        info["date_source"] = "weather_proposed"
        with session_scope() as s:
            s.get(Case, ctx.case_id).proposed_event_date = peak
        ctx.emit(
            "decision", "parse",
            f"मौसम के हिसाब से {date_hi(peak)} की तारीख़ मानकर जाँच हो रही है। कृपया इसकी पुष्टि करें।",
            f"Investigating {date_en(peak)}, proposed from the weather. Please confirm it.",
            proposed_event_date=peak,
        )
    return update


def route_after_parse(state: State) -> str:
    return "stop" if state.get("stop") else "resolve_plot"


# resolve_plot


def n_resolve_plot(state: State, ctx: Ctx) -> dict:
    case = state["case"]
    ctx.emit("step_started", "resolve_plot", "खेत की सीमा जाँची जा रही है", "Checking the field boundary")
    polygon = state.get("polygon")
    try:
        info: PlotInfo = _geo().plot_info(polygon)
    except Exception as exc:  # noqa: BLE001
        ctx.emit("error", "resolve_plot", "खेत की सीमा का इस्तेमाल नहीं हो सका। कृपया दोबारा बनाएँ।",
                 f"The field boundary could not be used: {exc}. Please redraw it.",
                 error=f"{type(exc).__name__}: {exc}", needs=["plot"])
        return {"stop": "needs_input"}
    event = EventInfo(
        type=case["event_type"] or "unknown", date=case["event_date"],
        date_source=case["date_source"] if case["date_source"] in (
            "farmer", "weather_proposed", "news") else "farmer",
        crop=case["crop"],
    )
    evidence = Evidence(
        case_id=ctx.case_id, run_id=ctx.run_id, created_at=datetime.now(UTC), plot=info, event=event,
    )
    ctx.emit(
        "tool_result", "resolve_plot",
        f"खेत: {info.area_ha:.2f} हेक्टेयर", f"Field: {info.area_ha:.2f} ha",
        tool="plot_info", result={"area_ha": info.area_ha, "centroid": info.centroid,
                                  "crs": info.crs, "warnings": info.warnings},
    )
    return {
        "evidence": evidence, "seed": make_seed(polygon, event.date),
        "post_days": POST_WINDOW_DAYS, "pre_days": PRE_WINDOW_DAYS,
        "excluded": [], "qa_seen": {}, "loops": 0, "attempted": [],
    }


def start_timeline(ctx: Ctx, polygon: dict, event_date: date) -> None:
    """Independent of every later decision and slow, so it runs in the background and is collected
    at the seal. It waits until the comparison is done, and reuses QA results from the geo cache."""
    if ctx.timeline_future is not None:
        return
    start = event_date - timedelta(days=PRE_WINDOW_DAYS)
    end = min(event_date + timedelta(days=POST_WINDOW_DAYS), today_ist())
    ctx.timeline_future = _TOOLS.submit(
        ctx.call, "seal", "timeline", lambda: _geo().timeline(polygon, start, end),
        "इस खेत के सभी सैटेलाइट दर्शन", "Every satellite pass over this field",
        summarize=lambda r: {"n_points": len(r), "points": [
            {"date": p.date, "sensor": p.sensor, "ndvi": p.ndvi, "vh_db": p.vh_db, "qa": p.qa}
            for p in r][:40]},
        start=start, end=end,
    )


def route_after_plot(state: State) -> str:
    return "stop" if state.get("stop") else "gather_context"


# gather_context


def _weather_titles(w) -> tuple[str, str]:
    rain = f"{w.max_daily_mm:.1f}" if w.max_daily_mm is not None else "-"
    if w.corroborated:
        return (f"मौसम मॉडल के अनुसार उस समय मौसम ख़राब था: दिन में अधिकतम {rain} मिमी",
                f"Weather model indicates bad weather: up to {rain} mm in a day")
    return (f"मौसम मॉडल में कोई ख़ास संकेत नहीं (अधिकतम {rain} मिमी)। छोटा तूफ़ान मॉडल से छूट सकता है।",
            f"No strong model signal (up to {rain} mm). A small storm can be missed by the model.")


def n_gather_context(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    ctx.emit("step_started", "gather_context", "मौसम, सरकारी चेतावनी और ख़बरें देखी जा रही हैं",
             "Checking weather, official alerts and news")
    lon, lat = ev.plot.centroid
    place: dict = {}
    try:
        place = ctx.call("gather_context", "locate", lambda: alerts.locate(lat, lon),
                         "खेत का ज़िला पता किया जा रहा है", "Finding the district of the field",
                         summarize=lambda r: r, counted=False)
    except ToolFailed:
        pass
    district, state_name = place.get("district"), place.get("state")
    if district or state_name:
        with session_scope() as s:
            row = s.get(Case, ctx.case_id)
            row.district, row.state = district, state_name

    def get_weather():
        return ctx.call(
            "gather_context", "weather",
            lambda: weather.fetch_weather(lat, lon, ev.event.date, ev.event.type),
            "मौसम मॉडल देखा जा रहा है", "Checking the weather model",
            summarize=lambda w: {
                "source": w.source, "max_daily_mm": w.max_daily_mm,
                "precip_mm_event_window": w.precip_mm_event_window,
                "hail_code_hours": w.hail_code_hours, "thunder_hours": w.thunder_hours,
                "max_gust_kmh": w.max_gust_kmh, "corroborated": w.corroborated,
                "proposed_event_date": w.proposed_event_date, "fallback_used": w.fallback_used,
                "signals": weather.corroboration_signals(w), "grid_note": w.grid_note,
            },
            event_date=ev.event.date,
        )

    def get_alerts():
        return ctx.call(
            "gather_context", "alerts",
            lambda: alerts.match(district, ev.event.date, ev.event.type),
            "सरकारी चेतावनियों का रिकॉर्ड देखा जा रहा है", "Checking the official alert archive",
            summarize=lambda r: {"matched": len(r), "district": district,
                                 "headlines": [a.headline for a in r][:3]},
            district=district,
        )

    def get_news():
        if not llm.available():
            ctx.emit("decision", "gather_context",
                     "ख़बरों की खोज के लिए LLM उपलब्ध नहीं, इसलिए यह जाँच छोड़ी गई",
                     "News search needs the LLM, which is not available, so it was skipped",
                     reason="no_llm")
            return []
        return ctx.call(
            "gather_context", "news",
            lambda: news.search(district, state_name, ev.event.type, ev.event.date),
            "ख़बरें खोजी जा रही हैं", "Searching the news",
            summarize=lambda r: {"found": len(r), "urls": [n.url for n in r][:5]},
            district=district,
        )

    futures = {name: _TOOLS.submit(fn) for name, fn in
               (("weather", get_weather), ("alerts", get_alerts), ("news", get_news))}
    results: dict = {}
    for name, future in futures.items():
        try:
            results[name] = future.result()
        except ToolFailed:
            results[name] = None
    w = results["weather"]
    if w is not None:
        ev.weather = w
        _prov(ev, "weather", w.source, url=get_settings().nasa_power_url if w.fallback_used
              else get_settings().open_meteo_historical_url, when=w.fetched_at)
        hi, en = _weather_titles(w)
        ctx.emit("decision", "gather_context", hi, en, corroborated=w.corroborated,
                 max_daily_mm=w.max_daily_mm, hail_code_hours=w.hail_code_hours,
                 max_gust_kmh=w.max_gust_kmh, grid_note=w.grid_note,
                 fallback_used=w.fallback_used)
        if w.fallback_used:
            ctx.emit("warning", "gather_context",
                     "Open-Meteo नहीं मिला, इसलिए NASA POWER का इस्तेमाल हुआ (इसमें ओलों का कोड नहीं होता)",
                     "Open-Meteo was unavailable, so NASA POWER was used (it has no hail codes)",
                     source=w.source)
    else:
        ctx.emit("warning", "gather_context", "मौसम का डेटा नहीं मिला; जाँच इसके बिना जारी है।",
                 "Weather data could not be retrieved; the investigation continues without it.")
    ev.alerts = results["alerts"] or []
    for a in ev.alerts:
        _prov(ev, f"alerts.{a.identifier}", a.source, asset=a.identifier, url=a.url)
    ev.news = results["news"] or []
    for item in ev.news:
        _prov(ev, "news", "Gemini Google Search grounding", url=item.url)
    return {"evidence": ev, "weather_payload_date": ev.event.date}


# planner


_PLAN_RATIONALE = {"rationale": {"type": "string", "description": "Why, in one sentence."}}
PLAN_OPTIONS = [
    {
        "name": "search_optical",
        "description": "Search Sentinel-2 optical scenes around the event and QA them. Usually first.",
        "parameters": {
            "type": "object",
            "properties": {
                "post_window_days": {"type": "integer", "description": "Days after the event, 10-30"},
                **_PLAN_RATIONALE,
            },
            "required": ["rationale"],
        },
    },
    {
        "name": "sar_first",
        "description": "Go to Sentinel-1 radar first, when persistent cloud makes optical unlikely.",
        "parameters": {"type": "object", "properties": _PLAN_RATIONALE, "required": ["rationale"]},
    },
]


def plan_veto(name: str, ev: Evidence) -> str | None:
    """Code-level guard over the LLM's choice. Returns the reason if vetoed."""
    if name == "sar_first":
        heavy = ev.weather is not None and ev.weather.corroborated
        if ev.event.type not in ("flood", "cyclone") and not heavy:
            return "radar-first needs a flood or cyclone report, or a heavy weather signal"
    return None


def n_planner(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    days_since = (today_ist() - ev.event.date).days
    default_hi = "पहले सैटेलाइट की साफ़ तस्वीरें खोजी जाएँगी"
    default_en = "Search for clear optical images first"
    if days_since < 1:
        default_hi = "घटना आज की है, इसलिए शायद बाद की तस्वीर अभी न मिले; पहले की तस्वीर खोजी जाएगी"
        default_en = "The event is from today, so an image after it may not exist yet; finding the image before it"
    update: dict = {"sar_first": False}
    choice = None
    if llm.available():
        w = ev.weather
        context = (
            f"Event type: {ev.event.type}. Reported date: {ev.event.date}. Days since: {days_since}. "
            f"Plot area: {ev.plot.area_ha} ha. Weather corroborated: {w.corroborated if w else None}. "
            f"Max daily rain: {w.max_daily_mm if w else None} mm. Tool calls left: {ctx.calls_left()}. "
            f"Seconds left: {round(ctx.seconds_left())}."
        )
        choice = llm.plan(context, PLAN_OPTIONS)
    if choice is not None:
        veto = plan_veto(choice.name, ev)
        if veto:
            ctx.emit("decision", "planner", "मॉडल का सुझाव जाँच-नियम से रद्द हुआ; तय रास्ता अपनाया गया",
                     f"Planner suggestion vetoed by a code guard: {veto}", suggested=choice.name,
                     veto=veto, rationale=choice.rationale, llm=True)
        else:
            ev.llm_used = True
            if choice.name == "sar_first":
                update["sar_first"] = True
            days = choice.args.get("post_window_days")
            if isinstance(days, int) and 10 <= days <= MAX_POST_WINDOW_DAYS:
                update["post_days"] = days
            ctx.emit("decision", "planner", f"योजना: {choice.name}", f"Plan: {choice.name}",
                     choice=choice.name, args=choice.args, rationale=choice.rationale, llm=True)
            return update
    ctx.emit("decision", "planner", default_hi, default_en, choice="search_optical", llm=False,
             post_window_days=state.get("post_days", POST_WINDOW_DAYS), days_since_event=days_since)
    return update


def route_after_planner(state: State) -> str:
    return "sensor_switch" if state.get("sar_first") else "search_optical"


# search_optical + QA


def _qa_with_trace(ctx: Ctx, polygon: dict, scene, previous: SceneQA | None, seen: dict[str, SceneQA]
                   ) -> SceneQA | None:
    geo = _geo()
    key = f"{scene.id}|{previous.id if previous else ''}"
    if key in seen:
        return seen[key]
    try:
        qa = ctx.call(
            "search_optical", "qa_scene", lambda: geo.qa_scene(scene, polygon, previous),
            f"{date_hi(scene.date)} की तस्वीर की जाँच", f"Checking the {date_en(scene.date)} image",
            summarize=lambda q: {
                "scene_id": q.id, "date": q.date, "status": q.status, "reasons": q.reasons,
                "metadata_cloud_pct": q.metadata_cloud_pct, "plot_valid_frac": q.plot_valid_frac,
                "context_ndvi_median": q.context_ndvi_median,
            },
            counted=False, scene_id=scene.id,
        )
    except ToolFailed:
        return None
    seen[key] = qa
    if qa.status == "rejected":
        ctx.emit(
            "scene_rejected", "search_optical",
            f"{date_hi(scene.date)} की तस्वीर हटा दी गई: {_reasons_hi(qa.reasons)}",
            f"Rejected the {date_en(scene.date)} image: {_reasons_en(qa.reasons)}",
            scene_id=qa.id, date=qa.date, reasons=qa.reasons,
            metadata_cloud_pct=qa.metadata_cloud_pct, context_ndvi_median=qa.context_ndvi_median,
        )
    elif qa.status == "suspect":
        ctx.emit(
            "warning", "search_optical",
            f"{date_hi(scene.date)} की तस्वीर संदिग्ध है: {_reasons_hi(qa.reasons)}। दूसरे सेंसर से पुष्टि चाहिए।",
            f"The {date_en(scene.date)} image is suspect and needs a second sensor: "
            f"{_reasons_en(qa.reasons)}",
            scene_id=qa.id, date=qa.date, reasons=qa.reasons,
        )
    return qa


def _prefetch_qa(polygon: dict, scenes: list, seen: dict[str, SceneQA]) -> None:
    """Fills the geo engine's per-scene QA cache in parallel. Results come from the trace walk
    below, which still applies the temporal check in order. A failure here costs nothing."""
    todo = [s for s in scenes if f"{s.id}|" not in seen]
    if len(todo) < 2:
        return
    futures = [_QA_POOL.submit(_geo().qa_scene, scene, polygon, None) for scene in todo]
    wait(futures, timeout=_TIMEOUTS_S["qa_scene"])


def n_search_optical(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    polygon = state["polygon"]
    event_date = ev.event.date
    today = today_ist()
    pre_days, post_days = state.get("pre_days", PRE_WINDOW_DAYS), state.get("post_days", POST_WINDOW_DAYS)
    excluded = set(state.get("excluded") or [])
    start, end = event_date - timedelta(days=pre_days), min(event_date + timedelta(days=post_days), today)
    ctx.emit("step_started", "search_optical",
             f"{date_hi(start)} से {date_hi(end)} तक की सैटेलाइट तस्वीरें खोजी जा रही हैं",
             f"Searching satellite images from {date_en(start)} to {date_en(end)}",
             start=start, end=end, excluded=sorted(excluded))
    had_pair = ev.optical.pre is not None and ev.optical.post is not None
    update: dict = {"evidence": ev, "keep_previous": False, "pre_scene": None, "post_scene": None}

    def no_pair():
        saved = state.get("before_redate")
        if saved:
            # The proposed date has no image pair yet, while the farmer's own date had one. The
            # farmer's account keeps its evidence, and the date stays a proposal to confirm.
            for name in ("event", "optical", "neighbours", "history", "weather", "sar"):
                setattr(ev, name, saved[name])
            update.update(keep_previous=True, before_redate=None, seed=saved["seed"],
                          history_date=saved["history_date"])
            ctx.emit("decision", "search_optical",
                     f"सुझाई गई तारीख़ के लिए तस्वीरों की जोड़ी अभी नहीं है, इसलिए आपकी बताई तारीख़ {date_hi(ev.event.date)} "
                     "का सबूत रखा गया। तारीख़ का सुझाव आपकी पुष्टि के लिए है।",
                     f"The proposed date has no image pair yet, so the evidence for your date, "
                     f"{date_en(ev.event.date)}, is kept. The proposed date is for you to confirm.",
                     action="redate_reverted", event_date=ev.event.date)
            return update
        if had_pair and state.get("loops"):
            ctx.emit("decision", "search_optical",
                     "कोई बेहतर तस्वीर नहीं मिली, इसलिए पिछला नतीजा ही रखा गया, और आपत्ति दर्ज रहेगी",
                     "No better image was found, so the previous result stands and the objection "
                     "remains conceded.")
            update["keep_previous"] = True
        return update

    geo = _geo()
    try:
        scenes = ctx.call(
            "search_optical", "search_optical",
            lambda: geo.search_optical(polygon, start, end),
            "Sentinel-2 तस्वीरों की खोज", "Sentinel-2 image search",
            summarize=lambda r: {"n_scenes": len(r), "scenes": [
                {"id": s.id, "date": s.date, "cloud_pct": s.cloud_pct} for s in r]},
            start=start, end=end,
        )
    except ToolFailed:
        ctx.archive_failed = True
        ev.optical.scenes_considered = ev.optical.scenes_considered or []
        return no_pair()

    usable = [s for s in scenes if s.id not in excluded]
    pre_list = sorted((s for s in usable if s.date <= event_date), key=lambda s: s.datetime, reverse=True)
    post_list = sorted((s for s in usable if s.date > event_date), key=lambda s: s.datetime)
    seen = state.get("qa_seen") or {}
    considered: dict[str, SceneQA] = {s.id: s for s in ev.optical.scenes_considered}
    qa_budget = MAX_QA_PER_SEARCH
    _prefetch_qa(polygon, [*pre_list[:QA_PREFETCH], *post_list[:QA_PREFETCH]], seen)

    walk_started = time.monotonic()
    pre_scene = pre_qa = pre_suspect = pre_suspect_qa = None
    for scene in pre_list:
        if qa_budget <= 0 or ctx.seconds_left() < 20 or time.monotonic() - walk_started > PRE_WALK_S:
            break
        qa_budget -= 1
        qa = _qa_with_trace(ctx, polygon, scene, None, seen)
        if qa is None:
            continue
        considered[qa.id] = qa
        if qa.status == "accepted":
            pre_scene, pre_qa = scene, qa
            break
        if qa.status == "suspect" and pre_suspect is None:
            pre_suspect, pre_suspect_qa = scene, qa
    if pre_scene is None and pre_suspect is not None:
        # A plot under water or similar is a real observation: compare it, and let the suspect status
        # and the wrong_plot objection speak. It can never count toward a strong verdict.
        pre_scene, pre_qa = pre_suspect, pre_suspect_qa

    post_scene = suspect = None
    for scene in post_list:
        if qa_budget <= 0 or ctx.seconds_left() < 20 or time.monotonic() - walk_started > QA_WALK_S:
            break
        qa_budget -= 1
        qa = _qa_with_trace(ctx, polygon, scene, pre_qa, seen)
        if qa is None:
            continue
        considered[qa.id] = qa
        if qa.status == "accepted":
            post_scene = scene
            break
        if qa.status == "suspect" and suspect is None:
            suspect = scene

    chosen_post = post_scene or suspect
    update["accepted_pre"] = pre_scene is not None
    update["accepted_post"] = chosen_post is not None
    ev.optical.scenes_considered = sorted(considered.values(), key=lambda q: q.date)
    update["qa_seen"] = seen
    if pre_scene is not None and chosen_post is not None:
        update["pre_scene"], update["post_scene"] = pre_scene, chosen_post
        update["before_redate"] = None
        ctx.emit(
            "decision", "search_optical",
            f"तुलना के लिए {date_hi(pre_scene.date)} और {date_hi(chosen_post.date)} की तस्वीरें चुनी गईं",
            f"Comparing the {date_en(pre_scene.date)} and {date_en(chosen_post.date)} images",
            pre=pre_scene.id, post=chosen_post.id,
            n_rejected=sum(1 for q in considered.values() if q.status == "rejected"),
        )
        return update
    return no_pair()


def route_after_search(state: State) -> str:
    if state.get("keep_previous"):
        return "cross_examine"
    if state.get("pre_scene") is not None and state.get("post_scene") is not None:
        return "optical_compare"
    return "sensor_switch"


# Radar


def _pick_sar_pairs(scenes: list, event_date: date) -> list[tuple]:
    """Same relative orbit and pass direction only. Nearest pair around the event first."""
    groups: dict[tuple, list] = {}
    for scene in scenes:
        groups.setdefault((scene.orbit_state, scene.relative_orbit), []).append(scene)
    pairs = []
    for members in groups.values():
        before = sorted((s for s in members if s.date <= event_date), key=lambda s: s.datetime)
        after = sorted((s for s in members if s.date > event_date), key=lambda s: s.datetime)
        if before and after:
            pairs.append((before[-1], after[0]))
    return sorted(pairs, key=lambda p: (p[1].date - p[0].date).days)


def run_sar(state: State, ctx: Ctx, node: str) -> Any:
    """Radar search and same-orbit pair comparison, as one tool call. Returns SarEvidence or None."""
    geo = _geo()
    polygon, seed = state["polygon"], state["seed"]
    event_date = state["evidence"].event.date
    start = event_date - timedelta(days=PRE_WINDOW_DAYS)
    end = min(event_date + timedelta(days=POST_WINDOW_DAYS), today_ist())
    try:
        scenes = ctx.call(
            node, "search_sar", lambda: geo.search_sar(polygon, start, end),
            "Sentinel-1 रडार की खोज", "Sentinel-1 radar search",
            summarize=lambda r: {"n_scenes": len(r), "scenes": [
                {"id": s.id, "date": s.date, "orbit": s.orbit_state, "relative_orbit": s.relative_orbit}
                for s in r]},
            start=start, end=end,
        )
    except ToolFailed:
        ctx.archive_failed = True
        return None
    pairs = _pick_sar_pairs(scenes, event_date)
    if not pairs:
        ctx.emit("warning", node, "एक ही कक्षा की रडार जोड़ी नहीं मिली", "No same-orbit radar pair around the event",
                 n_scenes=len(scenes))
        return None
    result = None
    for pre, post in pairs[:2]:
        try:
            result = ctx.call(
                node, "sar_compare",
                lambda pre=pre, post=post: geo.sar_compare(polygon, pre.id, post.id, seed),
                f"रडार तुलना: {date_hi(pre.date)} और {date_hi(post.date)}",
                f"Radar comparison: {date_en(pre.date)} and {date_en(post.date)}",
                summarize=lambda r: {
                    "usable": r.usable, "reason": r.reason, "vh_change_db": r.vh_change_db,
                    "vh_excess_db": r.vh_excess_db, "new_water_frac": r.new_water_frac,
                    "orbit_direction": r.orbit_direction, "relative_orbit": r.relative_orbit,
                    "placebo_p": r.placebo.p_value if r.placebo else None,
                    "n_placebos": r.placebo.n_placebos if r.placebo else None,
                },
                pre=pre.id, post=post.id,
            )
        except ToolTimedOut:
            break  # a slow archive will not be faster for the next pair, and the budget is finite
        except ToolFailed:
            continue
        if result.usable:
            return result
    return result


def _apply_sar(ev: Evidence, sar) -> None:
    if sar is None:
        return
    ev.sar = sar
    for scene_id in (sar.pre_scene_id, sar.post_scene_id):
        if scene_id:
            _prov(ev, "sar", f"{PC} (sentinel-1-rtc)", asset=scene_id)


def n_sensor_switch(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    rejected = [q for q in ev.optical.scenes_considered if q.status == "rejected"]
    if state.get("sar_first"):
        hi, en = "योजना के अनुसार पहले रडार देखा जाएगा", "As planned, going to radar first"
    elif ctx.archive_failed:
        hi = "ऑप्टिकल तस्वीरों का संग्रह जवाब नहीं दे रहा, इसलिए रडार पर जा रहे हैं"
        en = "The optical image archive is not responding, so trying radar"
    elif rejected:
        hi = f"{len(rejected)} ऑप्टिकल तस्वीरें ख़राब निकलीं और भरोसेमंद जोड़ी नहीं बनी, इसलिए रडार पर जा रहे हैं, जो बादलों के पार देखता है"
        en = f"{len(rejected)} optical images failed and no trustworthy pair remains, so switching to radar, which sees through cloud"
    else:
        hi = "भरोसेमंद ऑप्टिकल जोड़ी नहीं मिली, इसलिए रडार पर जा रहे हैं, जो बादलों के पार देखता है"
        en = "No trustworthy optical pair was found, so switching to radar, which sees through cloud"
    ctx.emit("sensor_switch", "sensor_switch", hi, en, frm="sentinel-2", to="sentinel-1",
             n_rejected=len(rejected), rejected=[{"id": q.id, "date": q.date, "reasons": q.reasons}
                                                 for q in rejected])
    return {}


def n_sar_compare(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    if state.get("sar_tried") and ev.sar is not None:
        return {}
    sar = run_sar(state, ctx, "sar_compare")
    _apply_sar(ev, sar)
    return {"evidence": ev, "sar_tried": True}


# optical_compare


def n_optical_compare(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    pre, post = state["pre_scene"], state["post_scene"]
    polygon, seed = state["polygon"], state["seed"]
    geo = _geo()
    ctx.emit("step_started", "optical_compare", "खेत की तुलना आसपास के मिलते-जुलते खेतों से हो रही है",
             "Comparing the field with look-alike fields nearby", pre=pre.id, post=post.id)

    def compare():
        return ctx.call(
            "optical_compare", "optical_compare",
            lambda: geo.optical_compare(polygon, pre.id, post.id, seed),
            "ऑप्टिकल तुलना और प्लेसिबो जाँच", "Optical comparison and placebo test",
            summarize=lambda r: {
                "plot_delta_ndvi": r[0].plot_delta_ndvi, "drop_frac": r[0].drop_frac,
                "within_plot_pattern": r[0].within_plot_pattern,
                "post_bare_fraction": r[0].post_bare_fraction,
                "neighbour_median_delta": r[1].neighbour_median_delta,
                "placebo_p": r[1].placebo.p_value if r[1].placebo else None,
                "n_placebos": r[1].placebo.n_placebos if r[1].placebo else None,
                "n_at_least_as_extreme": r[1].placebo.n_at_least_as_extreme if r[1].placebo else None,
                "gap_at_post": r[1].counterfactual.gap_at_post if r[1].counterfactual else None,
            },
            pre=pre.id, post=post.id, seed=seed,
        )

    update: dict = {"evidence": ev, "optical_failed": False}
    try:
        optical, neighbours = compare()
    except ToolFailed:
        update["optical_failed"] = True
    else:
        considered = ev.optical.scenes_considered
        ev.optical = OpticalEvidence(**{**optical.model_dump(exclude={"scenes_considered"}),
                                        "scenes_considered": []})
        ev.optical.scenes_considered = considered
        ev.neighbours = neighbours
        for name, scene in (("optical.pre", pre), ("optical.post", post)):
            _prov(ev, name, f"{PC} (sentinel-2-l2a)", asset=scene.id)
        placebo = neighbours.placebo
        if placebo is not None and ev.optical.plot_delta_ndvi is not None:
            ctx.emit(
                "decision", "optical_compare",
                f"आपके खेत में हरियाली का बदलाव {signed(ev.optical.plot_delta_ndvi)}। आसपास के "
                f"{placebo.n_placebos} मिलते-जुलते खेतों में से {placebo.n_at_least_as_extreme} में इतना या ज़्यादा।",
                f"Your field's greenness changed {signed(ev.optical.plot_delta_ndvi)}. "
                f"{placebo.n_at_least_as_extreme} of {placebo.n_placebos} look-alike fields changed as much.",
                plot_delta_ndvi=ev.optical.plot_delta_ndvi, p_value=placebo.p_value,
                insufficient_reason=placebo.insufficient_reason,
            )
        # Radar corroborates in parallel with history and the timeline. It does not run alongside
        # the optical comparison, which is the main evidence and is slowed badly by competing reads.
        if not state.get("sar_tried") and ctx.calls_left() >= 4 and ctx.seconds_left() > 30:
            ctx.sar_future = _TOOLS.submit(run_sar, state, ctx, "optical_compare")
            update["sar_tried"] = True
    return update


def route_after_compare(state: State) -> str:
    if state.get("optical_failed") and not state.get("sar_tried"):
        return "sensor_switch"
    return "history"


# history


def n_history(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    start_timeline(ctx, state["polygon"], ev.event.date)  # after the comparison, which it would slow
    if ev.optical.pre is None or ev.optical.plot_delta_ndvi is None:
        ctx.emit("decision", "history",
                 "इस साल की ऑप्टिकल तुलना नहीं है, इसलिए पिछले वर्षों से तुलना नहीं की गई",
                 "No optical comparison this year, so history was not compared",
                 reason="no_current_delta")
        return {}
    current, pre_ndvi = ev.optical.plot_delta_ndvi, ev.optical.pre.ndvi_median
    same_date = state.get("history_date") == ev.event.date and ev.history is not None
    if same_date:
        # The scene pair changed but not the calendar window, so only this year's side changes.
        history = ev.history
        if history.typical_delta is not None:
            history.excess_vs_history = round(current - history.typical_delta, 4)
        history.downweighted = any(
            y.pre_ndvi is not None and abs(y.pre_ndvi - pre_ndvi) > cross_exam.HISTORY_PRE_DIFF
            for y in history.years
        )
        return {"evidence": ev}
    if ctx.seconds_left() < 25 or ctx.calls_left() < 2:
        ctx.emit("warning", "history", "समय या बजट कम है, इसलिए पिछले वर्षों से तुलना छोड़ी गई",
                 "Short on time or budget, so the history comparison was skipped",
                 calls_left=ctx.calls_left(), seconds_left=round(ctx.seconds_left()))
        return {}
    geo = _geo()
    polygon = state["polygon"]
    try:
        history = ctx.call(
            "history", "history",
            lambda: geo.history(polygon, ev.event.date, current_delta=current,
                                current_pre_ndvi=pre_ndvi),
            "इसी खेत के पिछले वर्षों से तुलना", "Comparing with this field's past years",
            summarize=lambda h: {
                "years": [{"year": y.year, "pre_ndvi": y.pre_ndvi, "delta_ndvi": y.delta_ndvi,
                           "note": y.note} for y in h.years],
                "typical_delta": h.typical_delta, "excess_vs_history": h.excess_vs_history,
                "downweighted": h.downweighted, "note": h.note,
            },
        )
    except ToolFailed:
        return {}
    ev.history = history
    for scene_id in geo.history_scene_ids(history):
        _prov(ev, "history", f"{PC} (sentinel-2-l2a)", asset=scene_id)
    return {"evidence": ev, "history_date": ev.event.date}


# cross_examine


def _rephrase(objections: list) -> dict[str, tuple[str, str]]:
    if not llm.available():
        return {}
    raw = llm.rephrase_challenges(
        [{"id": o.id, "challenge_hi": o.challenge_hi, "challenge_en": o.challenge_en}
         for o in objections]
    )
    return raw or {}


def _pick_followup(state: State, ctx: Ctx, followups: list[cross_exam.FollowUp], ev: Evidence):
    """The first follow-up that could change something and that the budget can pay for."""
    if state.get("loops", 0) >= MAX_LOOPS:
        return None, "loop limit reached"
    if ctx.seconds_left() < 30:
        return None, "time budget nearly used"
    reserve = 1  # chips are part of the record, so one call stays reserved for them
    cost = 2  # another search and another comparison
    if ctx.calls_left() < cost + reserve:
        return None, "tool budget nearly used"
    attempted = set(state.get("attempted") or [])
    today = today_ist()
    for f in followups:
        key = f"{f.kind}:{f.scene_id or f.event_date or ''}"
        if key in attempted:
            continue
        if f.kind == "widen_post" and (
            state.get("post_days", POST_WINDOW_DAYS) >= MAX_POST_WINDOW_DAYS
            or ev.event.date + timedelta(days=state.get("post_days", POST_WINDOW_DAYS)) >= today
        ):
            continue
        if f.kind == "widen_pre" and (
            state.get("accepted_pre") or not state.get("accepted_post")
            or state.get("pre_days", PRE_WINDOW_DAYS) >= 45
        ):
            continue  # an older "before" image is only worth finding if an "after" image exists
        if f.kind == "redate" and ev.event.date_source != "farmer":
            continue
        return f, key
    return None, "nothing more to try"


def _collect_sar(ctx: Ctx, ev: Evidence) -> None:
    if ctx.sar_future is None:
        return
    future, ctx.sar_future = ctx.sar_future, None
    try:
        _apply_sar(ev, future.result(timeout=max(3.0, min(60.0, ctx.seconds_left()))))
    except FutureTimeout:
        ctx.emit("warning", "cross_examine", "रडार की तुलना समय पर नहीं आई; उसके बिना आगे बढ़ रहे हैं",
                 "The radar comparison did not arrive in time; continuing without it")
    except ToolFailed:
        pass


def n_cross_examine(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    _collect_sar(ctx, ev)
    ctx.emit("step_started", "cross_examine", "अब एक सख़्त सर्वेयर इस सबूत पर सवाल उठाएगा",
             "A hostile surveyor now attacks this evidence", round=state.get("loops", 0) + 1)
    objections, followups = cross_exam.run(ev, state.get("farmer_date"))
    rephrased = state.get("llm_rephrase") or _rephrase(objections)
    allowed = validate.collect_numbers(ev.model_dump(mode="json"))
    for objection in objections:
        if objection.id in rephrased:
            hi, en = rephrased[objection.id]
            if validate.validate_text(hi, allowed).ok and validate.validate_text(en, allowed).ok:
                objection.challenge_hi, objection.challenge_en = hi, en
                ev.llm_used = True
    ev.cross_examination = objections
    outcomes = dict(state.get("last_outcomes") or {})
    for objection in objections:
        signature = f"{objection.outcome}|{objection.finding_en}"
        if outcomes.get(objection.id) == signature:
            continue  # a later round only re-announces what its new data changed
        outcomes[objection.id] = signature
        ctx.emit(
            "objection", "cross_examine", objection.challenge_hi, objection.challenge_en,
            id=objection.id, test=objection.test, measured=objection.measured,
            outcome=objection.outcome, finding_hi=objection.finding_hi,
            finding_en=objection.finding_en, round=state.get("loops", 0) + 1,
        )
    followup, why = _pick_followup(state, ctx, followups, ev)
    update: dict = {"evidence": ev, "route": "verdict", "llm_rephrase": rephrased,
                    "last_outcomes": outcomes}
    if followup is None:
        if followups:
            ctx.emit("decision", "cross_examine", "और डेटा से यह आपत्ति नहीं सुलझेगी, इसलिए फ़ैसले की ओर",
                     f"More data cannot settle this now ({why}), so moving to the verdict",
                     reason=why, open_followups=[f.kind for f in followups])
        return update
    update["route"] = "search_optical"
    update["loops"] = state.get("loops", 0) + 1
    update["attempted"] = [*(state.get("attempted") or []), why]
    if followup.kind == "exclude_scene":
        update["excluded"] = [*(state.get("excluded") or []), followup.scene_id]
        hi, en = "आपत्ति सही निकली, इसलिए यह तस्वीर हटाकर दूसरी खोजी जा रही है", (
            f"The {followup.objection} objection stands, so dropping that image and searching for another")
    elif followup.kind == "widen_post":
        update["post_days"] = MAX_POST_WINDOW_DAYS
        hi, en = "बाद की तस्वीर नहीं मिली, इसलिए खोज का समय बढ़ाया जा रहा है", (
            "No image after the event, so widening the search window")
    elif followup.kind == "widen_pre":
        update["pre_days"] = 45
        hi, en = "पहले की तस्वीर नहीं मिली, इसलिए खोज का समय बढ़ाया जा रहा है", (
            "No image before the event, so widening the search window")
    else:
        proposed = followup.event_date
        update["before_redate"] = {
            "event": ev.event, "optical": ev.optical, "neighbours": ev.neighbours,
            "history": ev.history, "weather": ev.weather, "sar": ev.sar, "seed": state["seed"],
            "history_date": state.get("history_date"),
        }
        _redate(ev, proposed, ctx)
        update["seed"] = make_seed(state["polygon"], proposed)
        update["qa_seen"] = {}
        update["history_date"] = None
        update["sar_tried"] = False if ctx.calls_left() >= 5 else state.get("sar_tried")
        hi, en = (
            f"मौसम का संकेत {date_hi(proposed)} को है, इसलिए उस तारीख़ पर दोबारा जाँच हो रही है",
            f"The weather signal is on {date_en(proposed)}, so re-running the evidence for that date",
        )
    ctx.emit("decision", "cross_examine", hi, en, action=followup.kind, objection=followup.objection,
             scene_id=followup.scene_id, event_date=followup.event_date, note=followup.note,
             loop=update["loops"], calls_left=ctx.calls_left())
    return update


def _redate(ev: Evidence, proposed: date, ctx: Ctx) -> None:
    """Moves the evidence to the proposed date. The farmer's own date stays on the case, for the
    deadline and for the farmer to confirm or correct."""
    ev.event = ev.event.model_copy(update={"date": proposed, "date_source": "weather_proposed"})
    with session_scope() as s:
        s.get(Case, ctx.case_id).proposed_event_date = proposed
    if ev.weather is not None:
        # The scan window already covers this date, so it needs no new request.
        lon, lat = ev.plot.centroid
        try:
            ev.weather = weather.fetch_weather(lat, lon, proposed, ev.event.type)
        except weather.WeatherUnavailable:
            log.warning("could not re-read the weather for the proposed date")
    ev.optical = OpticalEvidence(scenes_considered=ev.optical.scenes_considered)
    ev.neighbours = None
    ev.history = None


def route_after_cross_examine(state: State) -> str:
    return state.get("route") or "verdict"


# verdict


def n_verdict(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    result = rubric.decide(ev)
    if ctx.archive_failed and result.level == "insufficient":
        result = replace(result, reasons=[rubric.ARCHIVE_UNREACHABLE])
    head_hi, head_en, head_te = explain.headlines(result.level, ev.event.type)
    from app.evidence.schema import Verdict

    ev.verdict = Verdict(
        level=result.level, headline_hi=head_hi, headline_en=head_en, headline_te=head_te,
        reasons=result.reasons, caveats=result.caveats,
        falsifiers_checked=result.falsifiers_checked, rubric_version=result.version,
    )
    ctx.emit("verdict", "verdict", head_hi, head_en, level=result.level, reasons=result.reasons,
             caveats=result.caveats, rubric_version=result.version,
             corroborated_by=rubric.corroboration(ev), conceded=rubric.conceded(ev))
    if result.schedule_recheck:
        latest = max((q.date for q in ev.optical.scenes_considered), default=today_ist())
        due = datetime.combine(
            max(latest + timedelta(days=SENTINEL2_REVISIT_DAYS), today_ist() + timedelta(days=1)),
            datetime.min.time(), UTC,
        )
        basis = "sentinel-2-revisit"
        if rubric.comparison_incomplete(ev) or ctx.archive_failed:
            due, basis = datetime.now(UTC) + timedelta(minutes=30), "archive-retry"
        ev.deadlines = [d for d in ev.deadlines if d.type != "recheck"]
        ev.deadlines.append(Deadline(type="recheck", due_at=due, basis=basis, status="open"))
    return {"evidence": ev}


# village


def n_village(state: State, ctx: Ctx) -> dict:
    """Signatures 1 and 2. They need GEO's exports; without them the fields stay an honest null."""
    ev: Evidence = state["evidence"]
    geo = _geo()
    village_fn = getattr(geo, "village_witness", None)
    fade_fn = getattr(geo, "scale_fade", None)
    pre, post = ev.optical.pre, ev.optical.post
    sar_pair = ev.sar is not None and ev.sar.usable and ev.sar.pre_scene_id and ev.sar.post_scene_id
    if village_fn is None and fade_fn is None:
        ctx.emit("warning", "village", "गाँव स्तर का हिसाब अभी उपलब्ध नहीं", "The village-level computation is not available",
                 reason="geo_not_exported")
        return {}
    if not ((pre and post) or sar_pair):
        ctx.emit("decision", "village", "बिना भरोसेमंद जोड़ी के गाँव स्तर का हिसाब नहीं हो सकता",
                 "No trustworthy image pair, so no village-level computation", reason="no_pair")
        return {}
    if ctx.calls_left() < 2 or ctx.seconds_left() < -DOCUMENTATION_GRACE_S + 20:
        ctx.emit("warning", "village", "बजट कम होने से गाँव स्तर का हिसाब छोड़ा गया",
                 "Skipped the village-level computation because the budget is low",
                 calls_left=ctx.calls_left(), seconds_left=round(ctx.seconds_left()))
        return {}
    polygon, seed = state["polygon"], state["seed"]
    pair_ids = (pre.scene_id, post.scene_id) if pre and post else (ev.sar.pre_scene_id, ev.sar.post_scene_id)
    sensor = "s2" if pre and post else "s1"
    out_dir = get_settings().artifacts_dir / ctx.case_id / ctx.run_id
    update: dict = {"evidence": ev}

    def run_village():
        return ctx.call(
            "village", "village_witness",
            lambda: _with_applicability(
                village_fn(polygon, pair_ids[0], pair_ids[1], seed, sensor), ev.claim_path
            ),
            "आसपास की फ़सल भूमि का हिसाब और दस खेतों का ड्रॉ",
            "Cropland around the plot, and the Ten-Field Draw",
            summarize=lambda v: {
                "affected_share": v.affected_share, "n_cropland_pixels": v.n_cropland_pixels,
                "radius_m": v.radius_m, "sensor": v.sensor,
                "ten_field_draw": v.lottery.model_dump(mode="json", exclude={"sample_draws"})
                if v.lottery else None,
            },
        )

    def run_fade():
        return ctx.call(
            "village", "scale_fade",
            lambda: fade_fn(polygon, pair_ids[0], pair_ids[1], out_dir, sensor),
            "वही बदलाव बड़े और बड़े खानों में", "The same change at coarser and coarser cells",
            summarize=lambda f: {"sensor": f.sensor, "statistic": f.statistic, "levels": [
                {"block_m": x.block_m, "plot_cell_value": x.plot_cell_value} for x in f.levels]},
        )

    village_future = _TOOLS.submit(run_village) if village_fn is not None else None
    fade_future = _TOOLS.submit(run_fade) if fade_fn is not None else None
    if village_future is not None:
        try:
            village = village_future.result()
            village.nearby_real_cases = _nearby_real_cases(ev, village.radius_m, ctx.case_id)
            ev.village = village
            _prov(ev, "village", f"{PC} (computed by the geo engine)", asset=f"{pair_ids[0]},{pair_ids[1]}")
            draw = village.lottery
            if draw is not None and not draw.insufficient_reason and (
                draw.average_p05 is not None and draw.average_p95 is not None
            ):
                _draw_line(ctx, draw)
        except ToolFailed:
            pass
    if fade_future is not None:
        try:
            fade = fade_future.result()
            root = get_settings().artifacts_dir.resolve()
            for level in fade.levels:
                level.chip_path = _relative_artifact(level.chip_path, root)
            ev.scale_fade = fade
            _fade_line(ctx, fade)
        except ToolFailed:
            pass
    return update


def _with_applicability(village, path):
    if village.lottery is not None and path is not None:
        village.lottery.rule_applicability = claim_path.draw_applicability(path.route)
    return village


def _draw_line(ctx: Ctx, draw) -> None:
    """The Ten-Field Draw in one line. It shows how far one draw's average can move, never that the
    rule is unfair, and it says whether the rule governs this route at all."""
    share = draw.share_below_half_of_plot
    n = draw.n_simulations
    low, high = draw.average_p05, draw.average_p95
    if draw.rule_applicability == "may_apply":
        hi = f"दस खेतों का ड्रॉ, {n} बार: दस खेतों का औसत {low:+.2f} से {high:+.2f} तक गया।"
        en = f"The Ten-Field Draw, {n} times: the average of ten parcels moved between {low:+.2f} and {high:+.2f}."
    else:
        hi = f"अगर यह नियम यहाँ लागू होता तो: दस खेतों का ड्रॉ, {n} बार, और औसत {low:+.2f} से {high:+.2f} तक गया।"
        en = (f"What this rule would do if it applied here: the Ten-Field Draw, {n} times, with the "
              f"average of ten parcels between {low:+.2f} and {high:+.2f}.")
    if share is not None and draw.plot_value is not None:
        hi += f" {share * 100:.0f}% बार औसत आपके खेत के बदलाव ({draw.plot_value:+.2f}) के आधे से भी कम रहा।"
        en += (f" In {share * 100:.0f}% of draws the average came to under half of your field's change "
               f"({draw.plot_value:+.2f}).")
    hi += " यह फ़सल भूमि पर हमारा अनुकरण है, असली सूचना-सूची या आँका गया नुकसान नहीं।"
    en += " This is our simulation on cropland, not the real intimation list or assessed crop loss."
    ctx.emit("decision", "village", hi, en, signature="ten_field_draw", n_simulations=n, average_p05=low,
             average_p95=high, share_below_half_of_plot=share, plot_value=draw.plot_value,
             n_candidate_parcels=draw.n_candidate_parcels, rule_applicability=draw.rule_applicability)


def _fade_line(ctx: Ctx, fade) -> None:
    levels = [x for x in fade.levels if x.plot_cell_value is not None]
    if len(levels) < 2:
        return
    first, last = levels[0], levels[-1]
    ctx.emit(
        "decision", "village",
        f"{first.block_m} मीटर पर आपके खेत का बदलाव {first.plot_cell_value:+.2f} है; {last.block_m} मीटर के खाने में "
        f"{last.plot_cell_value:+.2f}। यह हमारा चित्रण है, YES-TECH का नतीजा नहीं।",
        f"At {first.block_m} m your field's change is {first.plot_cell_value:+.2f}; in a {last.block_m} m cell it "
        f"is {last.plot_cell_value:+.2f}. Our illustration from public satellite data, not output of YES-TECH.",
        signature="vanishing", levels=[{"block_m": x.block_m, "value": x.plot_cell_value} for x in levels],
    )


def _nearby_real_cases(ev: Evidence, radius_m: int, case_id: str) -> int:
    """Other real cases in our DB within the radius, with the same event date. Nothing estimated."""
    from pyproj import Geod

    geod = Geod(ellps="WGS84")
    lon, lat = ev.plot.centroid
    count = 0
    with session_scope() as s:
        rows = s.execute(
            select(Plot.centroid_lon, Plot.centroid_lat, Case.id, Case.event_date)
            .join(Case, Case.id == Plot.case_id)
            .where(Case.id != case_id)
        ).all()
    for other_lon, other_lat, _cid, event_date in rows:
        if event_date is None or abs((event_date - ev.event.date).days) > 3:
            continue
        _, _, distance = geod.inv(lon, lat, other_lon, other_lat)
        # A re-entry of this same field is not a neighbour.
        if SAME_FIELD_M < distance <= radius_m:
            count += 1
    return count


# policy


def _rule_names_for(path) -> list[tuple[str, str]]:
    names = [("when_individual_cover_is_available", "Cover depends on State notification, which is unknown here")]
    if path.route in ("localized_addon", "post_harvest_addon"):
        names.insert(0, ("intimation_deadline", "How and when to report on this route"))
        names.append(("intimation_contents", "What the intimation must contain"))
        names.append(("channels", "Where to report"))
        names.append(("late_intimation", "What the guidelines say about intimation timing"))
    if path.route == "post_harvest_addon":
        names.append(("post_harvest_14_day", "Post-harvest cover for a crop drying in the field"))
    if path.route == "localized_addon":
        names.append(("twenty_five_percent_rule", "What happens when many fields report the same event"))
    if path.route == "area_yield_basic":
        names.insert(0, ("no_individual_intimation_for_widespread", "Why an individual intimation is not essential here"))
        names.append(("grievance", "Where to go if the unit's result looks wrong"))
    if path.route == "undetermined":
        names.append(("intimation_deadline", "The add-on rule, if it turns out to apply"))
        names.append(("no_individual_intimation_for_widespread", "The area-yield rule, if it turns out to apply"))
    names.append(("technology_and_evidence", "What role satellite evidence has in the guidelines"))
    return names


def n_policy(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    ctx.emit("step_started", "policy", "नियम देखे जा रहे हैं: आपके मामले पर कौन सा रास्ता लागू है",
             "Checking the rules: which route applies to this case")
    with session_scope() as s:
        case = s.get(Case, ctx.case_id)
        path, deadlines = claim_path.for_case(case, state["case"]["lang"])
    ev.claim_path = path
    ev.deadlines = [d for d in ev.deadlines if d.type != "intimation_72h"] + deadlines
    if policy.load_corpus() is None:
        ctx.emit("warning", "policy", "नीति के दस्तावेज़ उपलब्ध नहीं", "Policy corpus unavailable", reason=policy.UNAVAILABLE)
    else:
        ev.policy = policy.clauses_for_rules(_rule_names_for(path))
    hi_reason = claim_path.route_claim(path.insured, path.crop_stage, ev.event.type, ev.event.crop, "hi")
    en_reason = claim_path.route_claim(path.insured, path.crop_stage, ev.event.type, ev.event.crop, "en")
    ctx.emit(
        "decision", "policy",
        f"रास्ता: {path.route}. " + " ".join(hi_reason.reasons[:1]),
        f"Route: {path.route}. " + " ".join(en_reason.reasons[:1]),
        route=path.route, insured=path.insured, crop_stage=path.crop_stage,
        intimation=path.intimation, countdown_applies=path.countdown_applies,
        unknowns=path.unknowns, clause_ids=path.clause_ids, n_clauses=len(ev.policy),
    )
    return {"evidence": ev}


# act


def n_act(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    case_dict = {
        "id": ctx.case_id, "crop": state["case"]["crop"], "event_time": state["case"]["event_time"],
    }
    draft = actions.draft_intimation(case_dict, ev.model_dump(mode="json"), ev.claim_path,
                                     ev.deadlines)
    deadline = next((d for d in ev.deadlines if d.type == "intimation_72h"), None)
    recheck = next((d for d in ev.deadlines if d.type == "recheck"), None)
    with session_scope() as s:
        for old in s.scalars(select(Action).where(
            Action.case_id == ctx.case_id, Action.status == "open",
            Action.type.in_(("intimation_draft", "recheck")),
        )).all():
            s.delete(old)
        s.add(Action(case_id=ctx.case_id, type="intimation_draft", payload=draft, status="open",
                     due_at=deadline.due_at if deadline else None))
        if recheck is not None:
            s.add(Action(
                case_id=ctx.case_id, type="recheck", status="open", due_at=recheck.due_at,
                payload={"reason": ev.verdict.level if ev.verdict else None,
                         "basis": recheck.basis},
            ))
        case = s.get(Case, ctx.case_id)
        if case.status != "submitted":
            case.status = (
                "intimation_due" if ev.claim_path and ev.claim_path.countdown_applies
                else "rechecking" if recheck is not None else "open"
            )
    if draft.get("available"):
        ctx.emit("action", "act", "सूचना का मसौदा तैयार है। इसे आपको ख़ुद भेजना होगा।",
                 "The intimation draft is ready. You send it yourself; nothing was filed.",
                 action="intimation_draft", needed=draft.get("needed"),
                 deadline_status=draft.get("deadline_status"), due_at=draft.get("due_at"),
                 countdown_applies=ev.claim_path.countdown_applies if ev.claim_path else False)
    else:
        ctx.emit("warning", "act", "नीति के दस्तावेज़ उपलब्ध नहीं, इसलिए मसौदा नहीं बना",
                 "Policy corpus unavailable, so no draft was made", reason=draft.get("reason"))
    if recheck is not None:
        ctx.emit("action", "act",
                 f"अगली सैटेलाइट तस्वीर के लिए दोबारा जाँच {date_hi(recheck.due_at.date())} के आसपास तय है",
                 f"A re-check for the next satellite pass is scheduled around {date_en(recheck.due_at.date())}",
                 action="recheck", due_at=recheck.due_at)
    return {"evidence": ev}


# explain


def n_explain(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    ctx.emit("step_started", "explain", "नतीजा सरल भाषा में लिखा जा रहा है", "Writing the result in plain language")
    report = explain.explain(ev)
    testimony.fill(ev)
    ctx.emit("action", "explain", "समझाने का पाठ तैयार", "Explanation ready", action="explanation",
             report=report, llm_used=ev.llm_used, tts_available=llm.available())
    return {"evidence": ev}


# seal


def _relative_artifact(path: str | None, root) -> str | None:
    if not path:
        return path
    from pathlib import Path

    resolved = Path(path).resolve()
    return str(resolved.relative_to(root)) if resolved.is_relative_to(root) else path


def _refresh_draft(ctx: Ctx, state: State, ev: Evidence) -> None:
    """The draft is written before the seal, so the verify link is added once the hash exists."""
    case_dict = {"crop": state["case"]["crop"], "event_time": state["case"]["event_time"]}
    draft = actions.draft_intimation(case_dict, ev.model_dump(mode="json"), ev.claim_path, ev.deadlines)
    with session_scope() as s:
        row = s.scalars(
            select(Action).where(Action.case_id == ctx.case_id, Action.type == "intimation_draft",
                                 Action.status == "open")
        ).first()
        if row is not None:
            row.payload = draft


def n_seal(state: State, ctx: Ctx) -> dict:
    ev: Evidence = state["evidence"]
    polygon, seed = state["polygon"], state["seed"]
    geo = _geo()
    ctx.emit("step_started", "seal", "सबूत पर मुहर लगाई जा रही है", "Sealing the evidence")
    def do_chips():
        pre, post = ev.optical.pre, ev.optical.post
        if not (pre and post):
            return None
        out_dir = get_settings().artifacts_dir / ctx.case_id / ctx.run_id
        sar = ev.sar if ev.sar and ev.sar.usable else None
        return ctx.call(
            "seal", "render_chips",
            lambda: geo.render_chips(polygon, pre.scene_id, post.scene_id, out_dir,
                                     sar.pre_scene_id if sar else None,
                                     sar.post_scene_id if sar else None),
            "पहले और बाद की तस्वीरें बन रही हैं", "Rendering before and after images",
            summarize=lambda r: {"chips": [c.kind for c in r]},
        )

    chips_future = _TOOLS.submit(do_chips)
    try:
        chips = chips_future.result()
        if chips:
            root = get_settings().artifacts_dir.resolve()
            for chip in chips:
                chip.path = _relative_artifact(chip.path, root)
            ev.chips = chips
    except ToolFailed:
        pass
    if ctx.timeline_future is not None:
        try:
            wait_s = 3.0 if ctx.archive_failed else max(3.0, min(40.0, ctx.seconds_left()))
            ev.timeline = ctx.timeline_future.result(timeout=wait_s) or []
        except FutureTimeout:
            ctx.emit("warning", "seal", "सैटेलाइट दर्शनों की सूची समय पर नहीं बनी", "The list of satellite passes was not ready in time")
        except ToolFailed:
            pass

    pre_id = ev.optical.pre.scene_id if ev.optical.pre else None
    post_id = ev.optical.post.scene_id if ev.optical.post else None
    sar = ev.sar
    hist = ev.history
    core = ReplayCore(
        engine_version=geo.ENGINE_VERSION,
        polygon=polygon,
        event_date=ev.event.date,
        optical_pre_id=pre_id,
        optical_post_id=post_id,
        sar_pre_id=sar.pre_scene_id if sar else None,
        sar_post_id=sar.post_scene_id if sar else None,
        history_scene_ids=geo.history_scene_ids(hist) if hist else [],
        seed=seed,
        numbers=geo.flatten_numbers(
            ev.optical if pre_id and post_id else None, ev.neighbours, sar, hist
        ),
    )
    ev.replay = core
    ev.evidence_hash = evidence_hash(core)
    _refresh_draft(ctx, state, ev)
    ctx.emit("action", "seal",
             f"सबूत की मुहर: {ev.evidence_hash[:12]}। कोई भी इसे सार्वजनिक सैटेलाइट डेटा से दोबारा जाँच सकता है।",
             f"Evidence sealed: {ev.evidence_hash[:12]}. Anyone can recompute it from public satellite data.",
             action="sealed", evidence_hash=ev.evidence_hash, n_numbers=len(core.numbers))
    return {"evidence": ev}


def build_graph(ctx: Ctx):
    graph = StateGraph(State)
    nodes = {
        "parse": n_parse, "resolve_plot": n_resolve_plot, "gather_context": n_gather_context,
        "planner": n_planner, "search_optical": n_search_optical,
        "optical_compare": n_optical_compare, "sensor_switch": n_sensor_switch,
        "sar_compare": n_sar_compare, "history": n_history, "cross_examine": n_cross_examine,
        "verdict": n_verdict, "village": n_village, "policy": n_policy, "act": n_act,
        "explain": n_explain, "seal": n_seal,
    }
    for name, fn in nodes.items():
        graph.add_node(name, guard(name, ctx, fn))
    graph.set_entry_point("parse")
    graph.add_conditional_edges("parse", route_after_parse, {"stop": END, "resolve_plot": "resolve_plot"})
    graph.add_conditional_edges("resolve_plot", route_after_plot, {"stop": END, "gather_context": "gather_context"})
    graph.add_edge("gather_context", "planner")
    graph.add_conditional_edges(
        "planner", route_after_planner,
        {"search_optical": "search_optical", "sensor_switch": "sensor_switch"},
    )
    graph.add_conditional_edges(
        "search_optical", route_after_search,
        {"optical_compare": "optical_compare", "sensor_switch": "sensor_switch",
         "cross_examine": "cross_examine"},
    )
    graph.add_conditional_edges(
        "optical_compare", route_after_compare,
        {"history": "history", "sensor_switch": "sensor_switch"},
    )
    graph.add_edge("sensor_switch", "sar_compare")
    graph.add_edge("sar_compare", "history")
    graph.add_edge("history", "cross_examine")
    graph.add_conditional_edges(
        "cross_examine", route_after_cross_examine,
        {"search_optical": "search_optical", "verdict": "verdict"},
    )
    graph.add_edge("verdict", "policy")
    graph.add_edge("policy", "village")
    graph.add_edge("village", "act")
    graph.add_edge("act", "explain")
    graph.add_edge("explain", "seal")
    graph.add_edge("seal", END)
    return graph.compile()


def run_investigation(run_id: str, case_id: str, tracer: Tracer) -> str:
    """Runs the graph to its end. Returns the run's terminal status."""
    settings = get_settings()
    ctx = Ctx(run_id=run_id, case_id=case_id, tracer=tracer,
              budget_calls=settings.run_budget_tool_calls, budget_s=settings.run_budget_seconds)
    final = build_graph(ctx).invoke({"evidence": None}, config={"recursion_limit": 60})
    ev = final.get("evidence")
    if final.get("stop") == "needs_input" or ev is None:
        ctx.emit("done", "seal", "जाँच के लिए और जानकारी चाहिए", "More information is needed for the investigation",
                 status="needs_input")
        return "needs_input"
    ok = ev.evidence_hash is not None
    ctx.emit(
        "done", "seal", "जाँच पूरी हुई" if ok else "जाँच पूरी हुई, पर सबूत पर मुहर नहीं लग सकी",
        "Investigation complete" if ok else "Investigation complete, but the evidence could not be sealed",
        status="done" if ok else "failed", level=ev.verdict.level if ev.verdict else None,
        evidence_hash=ev.evidence_hash, calls_used=ctx.calls, elapsed_s=round(ctx.elapsed(), 1),
        llm_used=ev.llm_used, finished_at=utcnow(),
    )
    return "done" if ok else "failed"


__all__ = ["canonical_json", "evidence_hash", "make_seed", "run_investigation"]

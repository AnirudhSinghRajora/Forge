"""Two things Gemini may add after the verdict: a question about the statement, and a second look at
the images. Each is an exhibit state stored beside the record, outside the sealed core.

They run on their own threads and the seal never waits for them. They read a copy of the evidence and
write only their own entry in `exhibits`, which is not hashed and which the rubric never reads. Text
goes through the validator and fails closed: an entry says what was found, or that it is unavailable.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.agent import llm, validate, witness
from app.config import get_settings
from app.db import EvidenceRow, session_scope
from app.evidence.schema import Evidence

log = logging.getLogger(__name__)

IMAGE_OPINION = "image_opinion"
STATEMENT_CHECK = "statement_check"
NAMES = (IMAGE_OPINION, STATEMENT_CHECK)
STATEMENT_S = 30
IMAGE_S = llm.VISION_TIMEOUT_S + 15
STALE_S = 300.0  # a pending entry older than this lost its thread to a restart
MAX_CHIP_BYTES = 8_000_000
MAX_TEXT_CHARS = 600
QUESTION_ABOUT = ("date", "event", "crop_stage")
# The order the model reads them in.
CHIP_LABELS = (
    ("true_colour_pre", "true colour, before"), ("true_colour_post", "true colour, after"),
    ("ndvi_pre", "NDVI, before"), ("ndvi_post", "NDVI, after"),
)

# persist() in the graph and these threads both rewrite the row's exhibits. One process only (see
# limits.py), so this lock keeps either from overwriting the other.
ROW_LOCK = threading.Lock()
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="advisory")


def _entry(status: str, reason: str | None = None, **extra) -> dict:
    return {"status": status, "reason": reason, "updated_at": datetime.now(UTC).isoformat(), **extra}


def merged(stored: dict | None, current: dict) -> dict:
    """What a run may write: its own exhibits, with these entries as they stand in the database."""
    keep = {k: v for k, v in current.items() if k not in NAMES}
    keep.update({k: v for k, v in (stored or {}).items() if k in NAMES})
    return keep


def is_stale(entry: dict | None, now: datetime | None = None) -> bool:
    if not entry or entry.get("status") != "pending":
        return False
    try:
        began = datetime.fromisoformat(entry.get("updated_at") or "")
    except ValueError:
        return True
    return ((now or datetime.now(UTC)) - began).total_seconds() > STALE_S


def public(name: str, entry: dict) -> dict:
    """A thread that died at a restart does not leave the page saying this is still coming."""
    if name in NAMES and is_stale(entry):
        return _entry("failed", "no_answer")
    return entry


def _store(run_id: str, name: str, entry: dict) -> None:
    with ROW_LOCK, session_scope() as s:
        row = s.scalar(select(EvidenceRow).where(EvidenceRow.run_id == run_id))
        if row is not None:
            row.exhibits = {**(row.exhibits or {}), name: entry}


def image_facts(ev: Evidence) -> dict:
    o = ev.optical
    return {
        "ndvi_before": o.pre.ndvi_median if o.pre else None, "ndvi_after": o.post.ndvi_median if o.post else None,
        "date_before": o.pre.date.isoformat() if o.pre else None, "date_after": o.post.date.isoformat() if o.post else None,
        "change_in_ndvi": o.plot_delta_ndvi, "share_of_field_that_dropped": o.drop_frac,
        "bare_soil_share_after": o.post_bare_fraction, "pattern_within_field": o.within_plot_pattern,
    }


def _chip_images(ev: Evidence) -> list[tuple[str, bytes]]:
    root = get_settings().artifacts_dir.resolve()
    images = []
    for kind, label in CHIP_LABELS:
        chip = next((c for c in ev.chips if c.kind == kind), None)
        if chip is None:
            continue
        path = (root / chip.path).resolve()
        if path.is_relative_to(root) and path.is_file() and path.stat().st_size <= MAX_CHIP_BYTES:
            images.append((label, Path(path).read_bytes()))
    return images


def _usable(text: str, allowed: set[float], lang: str) -> bool:
    text = (text or "").strip()
    if not text or len(text) > MAX_TEXT_CHARS or not witness._in_script(text, lang):
        return False
    result = validate.validate_text(text, allowed)
    if not result.ok:
        log.warning("advisory text rejected by the validator: %s", result.reason())
    return result.ok


def run_image_opinion(run_id: str, ev: Evidence) -> None:
    images = _chip_images(ev)
    labels = [label for label, _ in images]
    if "true colour, before" not in labels or "true colour, after" not in labels:
        _store(run_id, IMAGE_OPINION, _entry("not_applicable", "no_images"))
        return
    facts = image_facts(ev)
    raw = llm.bounded(IMAGE_S, llm.read_images, images, facts)
    if raw is None:
        _store(run_id, IMAGE_OPINION, _entry("failed", "no_answer"))
        return
    allowed = validate.collect_numbers(facts)
    texts = {lang: getattr(raw, f"description_{lang}") for lang in ("hi", "en", "te")}
    if not all(_usable(text, allowed, lang) for lang, text in texts.items()):
        _store(run_id, IMAGE_OPINION, _entry("failed", "text_rejected"))
        return
    _store(run_id, IMAGE_OPINION, _entry("done", opinion={
        "description_hi": texts["hi"].strip(), "description_en": texts["en"].strip(), "description_te": texts["te"].strip(),
        "visible_change": raw.visible_change, "consistent": raw.consistent,
        # A model disagreeing with a measurement is never settled by either of them.
        "needs_person": raw.consistent == "no",
    }))


def statement_input(transcript: str | None, crop_stage: str | None, ev: Evidence) -> dict | None:
    """What the farmer said. None when there is nothing of theirs to compare."""
    said = {"transcript": transcript, "event_type": ev.event.type, "event_date": ev.event.date.isoformat(),
            "date_source": ev.event.date_source, "crop": ev.event.crop, "crop_stage": crop_stage}
    if not transcript and crop_stage in (None, "unknown"):
        return None
    return said


def statement_facts(ev: Evidence) -> dict:
    keep = ("event.", "optical.", "weather.", "corroboration.", "alerts.", "objection.harvest.", "objection.wrong_date.")
    facts = {k: v for k, v in witness.evidence_facts(ev).items() if k.startswith(keep) or k == "verdict.level"}
    days = ev.weather.days if ev.weather else []
    if days:
        facts["weather.rain_by_day_mm"] = {d.date.isoformat(): d.precip_mm for d in days}
    return facts


def run_statement_check(run_id: str, ev: Evidence, transcript: str | None, crop_stage: str | None) -> None:
    said = statement_input(transcript, crop_stage, ev)
    if said is None:
        _store(run_id, STATEMENT_CHECK, _entry("not_applicable", "no_statement"))
        return
    facts = statement_facts(ev)
    raw = llm.bounded(STATEMENT_S, llm.find_contradiction, said, facts)
    if raw is None:
        _store(run_id, STATEMENT_CHECK, _entry("failed", "no_answer"))
        return
    if not raw.found:
        _store(run_id, STATEMENT_CHECK, _entry("done", question=None))
        return
    allowed = witness.allowed_numbers(facts)
    texts = {lang: getattr(raw, f"question_{lang}") for lang in ("hi", "en", "te")}
    # It has to be a question about something the farmer can answer on the existing form.
    if (raw.about not in QUESTION_ABOUT or "?" not in texts["en"]
            or not all(_usable(text, allowed, lang) for lang, text in texts.items())):
        _store(run_id, STATEMENT_CHECK, _entry("failed", "text_rejected"))
        return
    _store(run_id, STATEMENT_CHECK, _entry("done", question={
        "about": raw.about, "hi": texts["hi"].strip(), "en": texts["en"].strip(), "te": texts["te"].strip(),
        "cited_fields": [f for f in raw.cited_fields if f in facts],
    }))


def _guarded(name: str, run_id: str, fn, *args) -> None:
    try:
        fn(run_id, *args)
    except Exception:  # nothing here may reach the run, or leave the entry pending
        log.exception("advisory %s failed for run %s", name, run_id)
        try:
            _store(run_id, name, _entry("failed", "no_answer"))
        except Exception:
            log.exception("could not record the failure of advisory %s", name)


def _claim(run_id: str, names: tuple[str, ...]) -> list[str]:
    """Marks entries pending and returns those this call now owns. Done or running ones are left be."""
    claimed = []
    with ROW_LOCK, session_scope() as s:
        row = s.scalar(select(EvidenceRow).where(EvidenceRow.run_id == run_id))
        if row is None:
            return []
        exhibits = dict(row.exhibits or {})
        for name in names:
            entry = exhibits.get(name)
            if entry is None or entry.get("status") == "failed" or is_stale(entry):
                exhibits[name] = _entry("pending")
                claimed.append(name)
        if claimed:
            row.exhibits = exhibits
    return claimed


def start(run_id: str, ev: Evidence, names: tuple[str, ...], transcript: str | None = None,
          crop_stage: str | None = None) -> list[str]:
    """Starts what has not run yet, and returns what it started. Nothing at all without a key, so the
    page says "not available" and no entry claims otherwise. Never raises into the caller."""
    if not llm.available():
        return []
    try:
        claimed = _claim(run_id, names)
        snapshot = ev.model_copy(deep=True) if claimed else None
        if IMAGE_OPINION in claimed:
            _POOL.submit(_guarded, IMAGE_OPINION, run_id, run_image_opinion, snapshot)
        if STATEMENT_CHECK in claimed:
            _POOL.submit(_guarded, STATEMENT_CHECK, run_id, run_statement_check, snapshot, transcript, crop_stage)
        return claimed
    except Exception:
        log.exception("could not start advisories for run %s", run_id)
        return []

"""Replay verification: re-download public satellite data and recompute every number live.

GET /api/verify/{hash} streams, in order: `start`, `progress` while the archive is re-read, one
`number` per field with stored vs recomputed, and a final `result`. Hash = sha256 of the canonical JSON (sorted keys) of ReplayCore, recomputed
from the stored core first: a tampered record is detected before any satellite data is fetched.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from sqlalchemy import select

from app.agent.graph import evidence_hash
from app.db import EvidenceRow, session_scope
from app.evidence.schema import ReplayCore

log = logging.getLogger(__name__)
TOLERANCE = 1e-3
PROGRESS_EVERY_S = 5.0
REPLAY_TIMEOUT_S = 300
UPSTREAM_EN = (
    "The public satellite archive could not be reached in time, so this could not be recomputed "
    "now. This says nothing about the evidence."
)
UPSTREAM_HI = (
    "सार्वजनिक सैटेलाइट संग्रह से समय पर संपर्क नहीं हो सका, इसलिए अभी दोबारा गणना नहीं हो सकी। इससे सबूत के बारे में कुछ "
    "तय नहीं होता।"
)


def _event(event_type: str, /, **data) -> dict:
    return {"event": "message", "data": json.dumps({"type": event_type, **data}, ensure_ascii=False)}


def load_core(hash_value: str) -> tuple[dict | None, str | None]:
    """Returns (stored core JSON, case id), or (None, None) if the hash is unknown."""
    with session_scope() as s:
        row = s.scalars(select(EvidenceRow).where(EvidenceRow.evidence_hash == hash_value)).first()
        if row is None:
            return None, None
        return row.replay_core, row.case_id


def compare_number(stored: float | None, recomputed: float | None, tolerance: float = TOLERANCE
                   ) -> bool:
    if stored is None or recomputed is None:
        return stored is None and recomputed is None
    return abs(stored - recomputed) <= tolerance


def compare_all(stored: dict, recomputed: dict, tolerance: float = TOLERANCE) -> list[dict]:
    rows = []
    for key in sorted(stored):
        if key not in recomputed:
            rows.append({"field": key, "stored": stored[key], "recomputed": None,
                         "match": False, "missing": True})
            continue
        rows.append({"field": key, "stored": stored[key], "recomputed": recomputed[key],
                     "match": compare_number(stored[key], recomputed[key], tolerance)})
    return rows


async def stream(hash_value: str) -> AsyncIterator[dict]:
    core_json, case_id = await asyncio.to_thread(load_core, hash_value)
    if core_json is None:
        yield _event("result", status="unknown_hash", ok=False,
                     message_en="No evidence record has this hash.",
                     message_hi="इस हैश का कोई सबूत रिकॉर्ड नहीं मिला।")
        return
    core = ReplayCore.model_validate(core_json)
    recomputed_hash = evidence_hash(core)
    if recomputed_hash != hash_value:
        yield _event("result", status="tampered", ok=False, stored_hash=hash_value,
                     recomputed_hash=recomputed_hash,
                     message_en="The stored record does not match its hash, so it was changed "
                                "after it was sealed.",
                     message_hi="रखा हुआ रिकॉर्ड अपने हैश से मेल नहीं खाता, यानी मुहर लगने के बाद इसे बदला गया है।")
        return
    yield _event(
        "start", hash=hash_value, hash_verified=True, case_id=case_id,
        engine_version=core.engine_version, event_date=core.event_date.isoformat(),
        optical_pre_id=core.optical_pre_id, optical_post_id=core.optical_post_id,
        sar_pre_id=core.sar_pre_id, sar_post_id=core.sar_post_id,
        history_scene_ids=core.history_scene_ids, seed=core.seed, n_numbers=len(core.numbers),
        tolerance=TOLERANCE, polygon=core.polygon,
    )
    if not core.numbers:
        yield _event("result", status="nothing_to_recompute", ok=True, n_numbers=0,
                     message_en="This record holds no satellite numbers to recompute.",
                     message_hi="इस रिकॉर्ड में दोबारा जाँचने के लिए सैटेलाइट के आँकड़े नहीं हैं।")
        return
    from app.tools import geo

    if geo.ENGINE_VERSION != core.engine_version:
        yield _event("note", kind="engine_version_differs", sealed=core.engine_version,
                     current=geo.ENGINE_VERSION,
                     message_en="This record was sealed by a different engine version, so numbers "
                                "could differ for that reason.",
                     message_hi="यह रिकॉर्ड इंजन के दूसरे संस्करण से बना था, इसलिए आँकड़े इस कारण भी अलग हो सकते हैं।")
    task = asyncio.create_task(asyncio.to_thread(geo.replay, core))
    started = time.monotonic()
    while True:
        done, _ = await asyncio.wait({task}, timeout=PROGRESS_EVERY_S)
        if done:
            break
        elapsed = time.monotonic() - started
        if elapsed > REPLAY_TIMEOUT_S:
            task.cancel()
            yield _event("result", status="upstream_unavailable", ok=False,
                         error=f"replay took longer than {REPLAY_TIMEOUT_S} s",
                         message_en=UPSTREAM_EN, message_hi=UPSTREAM_HI)
            return
        yield _event("progress", elapsed_s=round(elapsed),
                     message_en="Downloading the public satellite images again and recomputing.",
                     message_hi="सार्वजनिक सैटेलाइट तस्वीरें दोबारा डाउनलोड करके गणना हो रही है।")
    try:
        recomputed = task.result()
    except Exception as exc:  # noqa: BLE001  an upstream outage is reported as such, never as a mismatch
        log.warning("replay failed for %s: %s", hash_value, exc)
        yield _event("result", status="upstream_unavailable", ok=False,
                     error=f"{type(exc).__name__}: {exc}",
                     message_en=UPSTREAM_EN, message_hi=UPSTREAM_HI)
        return
    rows = compare_all(core.numbers, recomputed)
    for row in rows:
        yield _event("number", **row)
        await asyncio.sleep(0.03)
    matched = sum(1 for r in rows if r["match"])
    ok = matched == len(rows)
    yield _event(
        "result", status="verified" if ok else "mismatch", ok=ok, matched=matched, total=len(rows),
        mismatched=[r["field"] for r in rows if not r["match"]],
        message_en=f"{matched} of {len(rows)} numbers matched the public archive within {TOLERANCE}.",
        message_hi=f"{len(rows)} में से {matched} आँकड़े सार्वजनिक संग्रह से {TOLERANCE} के भीतर मेल खाए।",
    )

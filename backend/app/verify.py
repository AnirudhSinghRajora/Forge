"""Replay verification: re-download the public satellite data and recompute every number live.

GET /api/verify/{hash} streams, in order:
  start          the sealed record, including `numbers`, so a table can tick from stored to recomputed
  group_started  one group of numbers is being recomputed (optical, radar, history, village, scale)
  progress       a heartbeat while a group downloads
  number         stored vs recomputed for one field, as soon as its group finishes
  group_done     that group finished, or `group_failed` if it could not be read
  result         verified | mismatch | partial | upstream_unavailable | tampered | unknown_hash

Source of the numbers: every recomputation reads with fresh=True, which skips the memory and disk
caches and goes to the public archive over the network. Reading our own cache would prove nothing,
so `start` and each number state where the data came from, and a test pins this.

Hash = sha256 of the canonical JSON (sorted keys) of ReplayCore, recomputed from the stored core
first: a tampered record is detected before any satellite data is fetched.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Callable

from sqlalchemy import select

from app.agent.graph import evidence_hash
from app.db import EvidenceRow, cache_get, session_scope
from app.evidence.schema import ReplayCore

log = logging.getLogger(__name__)
TOLERANCE = 1e-3
PROGRESS_EVERY_S = 5.0
REPLAY_TIMEOUT_S = 480
SOURCE = {
    "archive": "public satellite archive",
    "read": "network",
    "cache": "bypassed (fresh=True)",
}
UPSTREAM_EN = (
    "The public satellite archive could not be reached in time, so this could not be recomputed "
    "now. This says nothing about the evidence."
)
UPSTREAM_HI = (
    "सार्वजनिक सैटेलाइट संग्रह से समय पर संपर्क नहीं हो सका, इसलिए अभी दोबारा गणना नहीं हो सकी। इससे सबूत के बारे में कुछ "
    "तय नहीं होता।"
)
# Which stored numbers each group answers for.
GROUP_PREFIXES = {
    "optical": ("optical.", "neighbours."),
    "radar": ("sar.",),
    "history": ("history.",),
    "village": ("village.",),
    "scale_fade": ("scale_fade.",),
}


def _event(event_type: str, /, **data) -> dict:
    return {"event": "message", "data": json.dumps({"type": event_type, **data}, ensure_ascii=False)}


def load_core(hash_value: str) -> tuple[dict | None, str | None, bool]:
    """Returns (stored core JSON, case id, superseded). A retried exhibit can reseal a record, and
    the earlier hash may be on a printed QR code, so it stays verifiable."""
    with session_scope() as s:
        row = s.scalars(select(EvidenceRow).where(EvidenceRow.evidence_hash == hash_value)).first()
        if row is not None:
            return row.replay_core, row.case_id, False
    old = cache_get(f"sealed:{hash_value}")
    return (old.payload, None, True) if old else (None, None, False)


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


def default_groups(core: ReplayCore) -> list[tuple[str, Callable[[], dict]]]:
    """One recomputation per group, each with fresh=True. Mirrors geo.replay, in streamable pieces."""
    from app.tools.geo.optical import _optical_compare, history_from_ids
    from app.tools.geo.replay import flatten_numbers
    from app.tools.geo.sar import _sar_compare
    from app.tools.geo.scale import _scale_fade
    from app.tools.geo.village import _village_witness

    groups: list[tuple[str, Callable[[], dict]]] = []
    numbers = core.numbers

    def pair(flag_key: str) -> tuple[str, str, str] | None:
        flag = numbers.get(flag_key)
        if flag is None:
            return None
        if flag == 1.0:
            return (core.sar_pre_id, core.sar_post_id, "s1") if core.sar_pre_id and core.sar_post_id else None
        return (core.optical_pre_id, core.optical_post_id, "s2") if core.optical_pre_id and core.optical_post_id else None

    if core.optical_pre_id and core.optical_post_id:
        def optical():
            o, n = _optical_compare(core.polygon, core.optical_pre_id, core.optical_post_id, core.seed,
                                    fresh=True)
            return flatten_numbers(o, n)
        groups.append(("optical", optical))
    if core.sar_pre_id and core.sar_post_id:
        groups.append(("radar", lambda: flatten_numbers(sar=_sar_compare(
            core.polygon, core.sar_pre_id, core.sar_post_id, core.seed, fresh=True))))
    if core.history_scene_ids:
        def history():
            with_current = numbers.get("history.excess_vs_history") is not None
            return flatten_numbers(history=history_from_ids(
                core.polygon, core.history_scene_ids,
                current_delta=numbers.get("optical.plot_delta_ndvi") if with_current else None,
                current_pre_ndvi=numbers.get("optical.pre.ndvi_median") if with_current else None,
                fresh=True,
            ))
        groups.append(("history", history))
    if (ids := pair("village.sensor_is_s1")) is not None:
        groups.append(("village", lambda: flatten_numbers(village=_village_witness(
            core.polygon, ids[0], ids[1], core.seed, ids[2], fresh=True))))
    if (fade_ids := pair("scale_fade.sensor_is_s1")) is not None:
        groups.append(("scale_fade", lambda: flatten_numbers(scale_fade=_scale_fade(
            core.polygon, fade_ids[0], fade_ids[1], None, fade_ids[2], fresh=True))))
    return groups


def _groups_for(core: ReplayCore) -> list[tuple[str, Callable[[], dict]]]:
    from app.tools import geo

    exported = getattr(geo, "replay_groups", None)
    if exported is not None:
        return list(exported(core))
    try:
        return default_groups(core)
    except ImportError:  # a stand-in geo module exposes only replay()
        return [("all", lambda: geo.replay(core))]


def _keys_of(group: str, numbers: dict) -> dict:
    if group == "all":
        return numbers
    prefixes = GROUP_PREFIXES.get(group, ())
    return {k: v for k, v in numbers.items() if k.startswith(prefixes)}


async def stream(hash_value: str) -> AsyncIterator[dict]:
    core_json, case_id, superseded = await asyncio.to_thread(load_core, hash_value)
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
        "start", hash=hash_value, hash_verified=True, case_id=case_id, superseded=superseded,
        engine_version=core.engine_version, event_date=core.event_date.isoformat(),
        optical_pre_id=core.optical_pre_id, optical_post_id=core.optical_post_id,
        sar_pre_id=core.sar_pre_id, sar_post_id=core.sar_post_id,
        history_scene_ids=core.history_scene_ids, seed=core.seed, n_numbers=len(core.numbers),
        numbers=core.numbers, tolerance=TOLERANCE, polygon=core.polygon, source=SOURCE,
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

    started = time.monotonic()
    checked: dict[str, dict] = {}
    errors: list[str] = []
    for group, compute in _groups_for(core):
        expected = _keys_of(group, core.numbers)
        if time.monotonic() - started > REPLAY_TIMEOUT_S:
            errors.append(f"{group}: time limit reached before it started")
            yield _event("group_failed", group=group, n_numbers=len(expected),
                         reason="time limit reached before it started")
            continue
        yield _event("group_started", group=group, n_numbers=len(expected), source=SOURCE)
        group_began = time.monotonic()
        task = asyncio.create_task(asyncio.to_thread(compute))
        timed_out = False
        while True:
            done, _ = await asyncio.wait({task}, timeout=PROGRESS_EVERY_S)
            if done:
                break
            if time.monotonic() - started > REPLAY_TIMEOUT_S:
                timed_out = True
                task.cancel()
                break
            yield _event("progress", group=group, elapsed_s=round(time.monotonic() - started),
                         message_en="Downloading the public satellite images again and recomputing.",
                         message_hi="सार्वजनिक सैटेलाइट तस्वीरें दोबारा डाउनलोड करके गणना हो रही है।")
        if timed_out:
            errors.append(f"{group}: time limit reached")
            yield _event("group_failed", group=group, n_numbers=len(expected), reason="time limit reached")
            continue
        try:
            recomputed = task.result()
        except Exception as exc:  # noqa: BLE001  an upstream outage is reported as such, never as a mismatch
            log.warning("replay group %s failed for %s: %s", group, hash_value, exc)
            errors.append(f"{group}: {type(exc).__name__}: {exc}")
            yield _event("group_failed", group=group, n_numbers=len(expected),
                         reason=f"{type(exc).__name__}: {exc}")
            continue
        for row in compare_all(expected, recomputed):
            checked[row["field"]] = row
            yield _event("number", group=group, source=SOURCE["read"], **row)
            await asyncio.sleep(0.01)
        yield _event("group_done", group=group, n_numbers=len(expected),
                     elapsed_s=round(time.monotonic() - group_began, 1))

    total = len(core.numbers)
    n_checked = len(checked)
    matched = sum(1 for r in checked.values() if r["match"])
    mismatched = [k for k, r in checked.items() if not r["match"]]
    unchecked = [k for k in sorted(core.numbers) if k not in checked]
    if n_checked == 0:
        yield _event("result", status="upstream_unavailable", ok=False, checked=0, total=total,
                     matched=0, mismatched=[], unchecked=unchecked, errors=errors,
                     error=errors[0] if errors else None,
                     message_en=UPSTREAM_EN, message_hi=UPSTREAM_HI)
        return
    status = "mismatch" if mismatched else ("partial" if unchecked else "verified")
    yield _event(
        "result", status=status, ok=status == "verified", checked=n_checked, matched=matched,
        total=total, mismatched=mismatched, unchecked=unchecked, errors=errors,
        elapsed_s=round(time.monotonic() - started), source=SOURCE,
        message_en=f"{n_checked} of {total} numbers checked against the public archive; "
                   f"{matched} matched within {TOLERANCE}.",
        message_hi=f"{total} में से {n_checked} आँकड़े सार्वजनिक संग्रह से जाँचे गए; {matched} {TOLERANCE} के भीतर मेल खाए।",
    )

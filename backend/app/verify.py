"""Public verification: re-download the satellite data and recompute the sealed numbers, cheapest first.

The recomputation runs as a background job, independent of any client, one job per hash. A client
watches it over SSE from GET /api/verify/{hash}, and can leave and return with ?after=seq.

Groups, in order, each with its own time budget, so a slow one cannot starve the rest:
  field_pre, field_post     only the plot's own window: NDVI statistics and the change
  field_extra               the same window: bare soil and red edge
  sar_field                 radar plot medians
  history                   the plot's past years
  ring                      nearby look-alike fields, in a window kilometres wide
  far_twin                  distant fields, the field's twin, the pre-event trend
  radar                     radar placebo and water
  village, scale_fade       the Ten-Field Draw and the coarse-cell view

Events, each with a monotonic `seq`:
  start           the sealed record: `numbers`, `scene_archives`, `source`, `groups`, `last_full_check`
  group_started   a group began
  progress        a heartbeat while a group downloads
  number          stored vs recomputed for one field, as soon as its group finishes
  group_done      that group finished
  group_failed    it could not finish, with `fields` naming exactly what stayed unchecked
  stage_result    field_verified | field_mismatch | field_engine_changed | field_failed, with the honest count so far
  note            kind=source says whether GDAL's HTTP cache was emptied first; kind=engine_version_differs
  result          final: verified | mismatch | engine_changed | field_verified | partial | upstream_unavailable
                  (engine_changed: a number differs, and the record was sealed by another engine version)

Nothing is called verified overall until every number is. Without a sealed core to work on, the only
event is a `result` with status unknown_hash, tampered or archive_mismatch.

Source of the numbers: every recomputation reads with fresh=True, which skips the memory and disk
caches, and a job first empties GDAL's HTTP block cache, so the bytes come over the network from the
archive recorded for that scene in the sealed record. Reading our own cache would prove nothing, so
events state where the data came from and a test pins it. A repeat scan of a fully checked record shows that stored check, labelled with its time and
`cached: true`; ?rerun=1 runs it again.

Hash = sha256 of the canonical JSON (sorted keys) of ReplayCore, recomputed from the stored core
first: a tampered record is detected before any satellite data is fetched.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.agent.graph import evidence_hash
from app.db import (
    EvidenceRow,
    VerifyEvent,
    VerifyRun,
    cache_get,
    new_id,
    session_scope,
    utcnow,
)
from app.evidence.schema import ReplayCore

log = logging.getLogger(__name__)
TOLERANCE = 1e-3
PROGRESS_EVERY_S = 5.0
POLL_S = 0.25
MAX_JOBS = 2  # the link is the limit, and a job already runs one group at a time
SOURCE = {
    "archive": "public satellite archive recorded for each scene",
    "read": "network",
    "cache": "bypassed (fresh=True)",
    "session": "blocks downloaded during this check are reused within it; nothing older is read",
}
# Generous for this link, and only for this group: when one runs out, the next one still starts.
GROUP_BUDGET_S = {
    "field_pre": 180, "field_post": 180, "field_extra": 300, "sar_field": 180, "history": 360, "ring": 420,
    "far_twin": 600, "radar": 420, "village": 420, "scale_fade": 360, "optical": 600, "all": 600,
}
DEFAULT_BUDGET_S = 420
UPSTREAM_EN = (
    "The public satellite archive could not be reached in time, so this could not be recomputed "
    "now. This says nothing about the evidence."
)
UPSTREAM_HI = (
    "सार्वजनिक सैटेलाइट संग्रह से समय पर संपर्क नहीं हो सका, इसलिए अभी दोबारा गणना नहीं हो सकी। इससे सबूत के बारे में कुछ "
    "तय नहीं होता।"
)
FIELD_GROUPS = ("field_pre", "field_post", "field_extra")
_FIELD_PLOT_STATS = ("valid_frac", "n_pixels", "ndvi_median", "ndvi_p25", "ndvi_p75")
_SAR_FIELD_KEYS = {"sar.vv_pre_db", "sar.vv_post_db", "sar.vh_pre_db", "sar.vh_post_db", "sar.vh_change_db"}
_RING_PREFIXES = ("neighbours.placebo.",)
_RING_KEYS = {
    "neighbours.ring_outer_m", "neighbours.n_comparable_pixels", "neighbours.neighbour_median_delta",
    "neighbours.plot_minus_neighbour", "neighbours.neighbour_bare_fraction_post",
}
# Older group names, for an exported geo.replay_groups or a stand-in engine in tests.
GROUP_PREFIXES = {
    "optical": ("optical.", "neighbours."),
    "radar": ("sar.",),
    "history": ("history.",),
    "village": ("village.",),
    "scale_fade": ("scale_fade.",),
}

_jobs = ThreadPoolExecutor(max_workers=MAX_JOBS, thread_name_prefix="verify-job")
_group_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="verify-group")
_start_lock = threading.Lock()


@dataclass(frozen=True)
class Group:
    name: str
    compute: Callable[[], dict]
    select: Callable[[str], bool]


def clear_http_cache() -> bool:
    """Empties GDAL's in-process HTTP block cache, which `fresh=True` does not reach.

    Our own memory and disk caches are skipped by fresh=True, but GDAL keeps recently fetched blocks
    per signed URL, and a scan right after an investigation could otherwise be answered from them.
    Cleared when a verification starts, so what it reads was downloaded by this verification. Groups
    within one verification do share blocks, which is why the ring is fast after the field stage.
    Returns False if the call is not available, and that is reported in `source`.
    """
    try:
        import ctypes
        from pathlib import Path

        import rasterio

        libs = Path(rasterio.__file__).parent.parent / "rasterio.libs"
        library = next(libs.glob("libgdal*"), None)
        handle = ctypes.CDLL(str(library)) if library else ctypes.CDLL("libgdal.so")
        handle.VSICurlClearCache()
        return True
    except (OSError, AttributeError) as exc:
        log.warning("could not clear GDAL's HTTP cache: %s", exc)
        return False


def _is_field_pre(key: str) -> bool:
    return any(key == f"optical.pre.{stat}" for stat in _FIELD_PLOT_STATS)


def _is_field_post(key: str) -> bool:
    if key in {"optical.plot_delta_ndvi", "optical.drop_frac", "optical.iqr_delta"}:
        return True
    return any(key == f"optical.post.{stat}" for stat in _FIELD_PLOT_STATS)


def _is_field_extra(key: str) -> bool:
    return key.startswith("optical.") and not (_is_field_pre(key) or _is_field_post(key))


def _is_ring(key: str) -> bool:
    return key in _RING_KEYS or key.startswith(_RING_PREFIXES)


def _is_far_twin(key: str) -> bool:
    return key.startswith("neighbours.") and not _is_ring(key)


def _is_radar(key: str) -> bool:
    return key.startswith("sar.") and key not in _SAR_FIELD_KEYS


def default_groups(core: ReplayCore) -> list[Group]:
    """Every group reads with fresh=True. The order is what makes numbers appear from the start."""
    from app.tools import geo
    from app.tools.geo.optical import _optical_compare, history_from_ids
    from app.tools.geo.replay import flatten_numbers
    from app.tools.geo.sar import _sar_compare
    from app.tools.geo.scale import _scale_fade
    from app.tools.geo.village import _village_witness

    numbers = core.numbers
    groups: list[Group] = []

    def pair(flag_key: str) -> tuple[str, str, str] | None:
        flag = numbers.get(flag_key)
        if flag is None:
            return None
        if flag == 1.0:
            return (core.sar_pre_id, core.sar_post_id, "s1") if core.sar_pre_id and core.sar_post_id else None
        return (core.optical_pre_id, core.optical_post_id, "s2") if core.optical_pre_id and core.optical_post_id else None

    if core.optical_pre_id and core.optical_post_id:
        field: list = []

        def replay_object():  # shared, so the field groups read each band once
            if not field:
                field.append(geo.FieldReplay(core.polygon, core.optical_pre_id, core.optical_post_id))
            return field[0]

        groups.append(Group("field_pre", lambda: replay_object().pre_stats(), _is_field_pre))
        groups.append(Group("field_post", lambda: replay_object().post_stats(), _is_field_post))
        groups.append(Group("field_extra", lambda: replay_object().extra(), _is_field_extra))
    if core.sar_pre_id and core.sar_post_id:
        groups.append(Group(
            "sar_field",
            lambda: geo.replay_sar_field(core.polygon, core.sar_pre_id, core.sar_post_id),
            lambda key: key in _SAR_FIELD_KEYS,
        ))
    if core.history_scene_ids:
        def history():
            with_current = numbers.get("history.excess_vs_history") is not None
            return flatten_numbers(history=history_from_ids(
                core.polygon, core.history_scene_ids,
                current_delta=numbers.get("optical.plot_delta_ndvi") if with_current else None,
                current_pre_ndvi=numbers.get("optical.pre.ndvi_median") if with_current else None,
                fresh=True,
            ))
        groups.append(Group("history", history, lambda key: key.startswith("history.")))
    if core.optical_pre_id and core.optical_post_id:
        groups.append(Group(
            "ring",
            lambda: flatten_numbers(neighbours=_optical_compare(
                core.polygon, core.optical_pre_id, core.optical_post_id, core.seed, fresh=True,
                with_twin=False, with_far=False,
            )[1]),
            _is_ring,
        ))
        groups.append(Group(
            "far_twin",
            lambda: flatten_numbers(neighbours=_optical_compare(
                core.polygon, core.optical_pre_id, core.optical_post_id, core.seed, fresh=True,
            )[1]),
            _is_far_twin,
        ))
    if core.sar_pre_id and core.sar_post_id:
        groups.append(Group(
            "radar",
            lambda: flatten_numbers(sar=_sar_compare(
                core.polygon, core.sar_pre_id, core.sar_post_id, core.seed, fresh=True,
            )),
            _is_radar,
        ))
    if (ids := pair("village.sensor_is_s1")) is not None:
        groups.append(Group(
            "village",
            lambda: flatten_numbers(village=_village_witness(
                core.polygon, ids[0], ids[1], core.seed, ids[2], fresh=True,
            )),
            lambda key: key.startswith("village."),
        ))
    if (fade_ids := pair("scale_fade.sensor_is_s1")) is not None:
        groups.append(Group(
            "scale_fade",
            lambda: flatten_numbers(scale_fade=_scale_fade(
                core.polygon, fade_ids[0], fade_ids[1], None, fade_ids[2], fresh=True,
            )),
            lambda key: key.startswith("scale_fade."),
        ))
    return groups


def _groups_for(core: ReplayCore) -> list[Group]:
    from app.tools import geo

    exported = getattr(geo, "replay_groups", None)
    if exported is not None:
        return [
            Group(name, fn, lambda key, name=name: key.startswith(GROUP_PREFIXES.get(name, ())))
            for name, fn in exported(core)
        ]
    if not hasattr(geo, "__path__"):  # a stand-in module in tests exposes only replay()
        return [Group("all", lambda: geo.replay(core), lambda key: True)]
    return default_groups(core)


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


class _Job:
    """One recomputation. Every event is stored before it is seen, so clients can come and go."""

    def __init__(self, run_id: str, hash_value: str, core: ReplayCore):
        self.run_id, self.hash, self.core = run_id, hash_value, core
        self.seq = 0

    def emit(self, event_type: str, /, **data) -> None:
        self.seq += 1
        payload = {"type": event_type, "seq": self.seq, "run_id": self.run_id, **data}
        with session_scope() as s:
            s.add(VerifyEvent(run_id=self.run_id, seq=self.seq, payload=payload))

    def finish(self, status: str, **data) -> None:
        self.emit("result", status=status, **data)
        with session_scope() as s:
            run = s.get(VerifyRun, self.run_id)
            run.status = status
            run.finished_at = utcnow()
            run.checked = data.get("checked")
            run.total = data.get("total")

    def run(self) -> None:
        try:
            from app.tools import geo

            # Every group in this check shares what the check itself downloads, and nothing older.
            with geo.fresh_session():
                self._run()
        except Exception as exc:
            log.exception("verify job %s failed", self.run_id)
            self.finish("partial", ok=False, checked=0, total=len(self.core.numbers),
                        unchecked=sorted(self.core.numbers), errors=[f"{type(exc).__name__}: {exc}"],
                        message_en="The check stopped unexpectedly. This says nothing about the evidence.",
                        message_hi="जाँच बीच में रुक गई। इससे सबूत के बारे में कुछ तय नहीं होता।")

    def _run(self) -> None:
        from app.tools import geo

        core = self.core
        self.emit("note", kind="source", http_cache_cleared=clear_http_cache(), source=SOURCE,
                  scene_archives=core.scene_archives)
        if geo.ENGINE_VERSION != core.engine_version:
            self.emit("note", kind="engine_version_differs", sealed=core.engine_version,
                      current=geo.ENGINE_VERSION,
                      message_en="This record was sealed by a different engine version, so numbers "
                                 "could differ for that reason.",
                      message_hi="यह रिकॉर्ड इंजन के दूसरे संस्करण से बना था, इसलिए आँकड़े इस कारण भी अलग हो सकते हैं।",
                      message_te="ఈ రికార్డు ఇంజిన్ వేరే వెర్షన్‌తో తయారైంది, కాబట్టి ఈ కారణంగా కూడా సంఖ్యలు వేరుగా ఉండవచ్చు.")
        groups = _groups_for(core)
        total = len(core.numbers)
        checked: dict[str, dict] = {}
        errors: dict[str, str] = {}
        assigned: set[str] = set()
        field_keys = {k for g in groups if g.name in FIELD_GROUPS for k in core.numbers if g.select(k)}
        started = time.monotonic()
        last_field = max((i for i, g in enumerate(groups) if g.name in FIELD_GROUPS), default=None)

        for position, group in enumerate(groups):
            # A key belongs to the first group claiming it, so no number is counted twice.
            expected = {k: v for k, v in core.numbers.items() if group.select(k) and k not in assigned}
            assigned |= set(expected)
            budget = GROUP_BUDGET_S.get(group.name, DEFAULT_BUDGET_S)
            self.emit("group_started", group=group.name, n_numbers=len(expected), source=SOURCE,
                      budget_s=budget)
            began = time.monotonic()
            future = _group_pool.submit(group.compute)
            recomputed = None
            failure = None
            while True:
                try:
                    recomputed = future.result(timeout=PROGRESS_EVERY_S)
                    break
                except FutureTimeout:
                    if future.done():  # the work itself raised a timeout, as opposed to still running
                        failure = f"{type(future.exception()).__name__}: {future.exception()}"
                        break
                    if time.monotonic() - began > budget:
                        failure = f"time budget of {budget} s reached"
                        break
                    self.emit("progress", group=group.name, elapsed_s=round(time.monotonic() - started),
                              message_en="Downloading the public satellite images again and recomputing.",
                              message_hi="सार्वजनिक सैटेलाइट तस्वीरें दोबारा डाउनलोड करके गणना हो रही है।")
                except Exception as exc:  # noqa: BLE001  an outage is reported, never as a mismatch
                    log.warning("verify group %s failed for %s: %s", group.name, self.hash, exc)
                    failure = f"{type(exc).__name__}: {exc}"
                    break
            if failure is not None:
                errors[group.name] = failure
                self.emit("group_failed", group=group.name, n_numbers=len(expected), reason=failure,
                          fields=sorted(expected), elapsed_s=round(time.monotonic() - began, 1))
            else:
                for row in compare_all(expected, recomputed):
                    checked[row["field"]] = row
                    # `field` is the sealed key; `label` is what to show, under the user-facing name.
                    label = row["field"].replace("village.lottery.", "village.ten_field_draw.")
                    self.emit("number", group=group.name, source=SOURCE["read"], label=label, **row)
                self.emit("group_done", group=group.name, n_numbers=len(expected),
                          elapsed_s=round(time.monotonic() - began, 1))
            if position == last_field:
                self._stage(field_keys, checked)

        unchecked = sorted(k for k in core.numbers if k not in checked)
        matched = sum(1 for r in checked.values() if r["match"])
        mismatched = sorted(k for k, r in checked.items() if not r["match"])
        n_checked = len(checked)
        common = {
            "checked": n_checked, "matched": matched, "total": total, "mismatched": mismatched,
            "unchecked": unchecked, "errors": errors, "source": SOURCE,
            "elapsed_s": round(time.monotonic() - started),
            "field_verified": bool(field_keys) and all(
                k in checked and checked[k]["match"] for k in field_keys),
        }
        if n_checked == 0:
            self.finish("upstream_unavailable", ok=False, error=next(iter(errors.values()), None),
                        message_en=UPSTREAM_EN, message_hi=UPSTREAM_HI, **common)
            return
        if mismatched:
            status = "engine_changed" if self._engine_differs() else "mismatch"
        elif not unchecked:
            status = "verified"
        elif common["field_verified"]:
            status = "field_verified"
        else:
            status = "partial"
        if status == "engine_changed":
            self.finish(status, ok=False, sealed_engine=self.core.engine_version,
                        current_engine=self._current_engine(),
                        **_engine_changed_text(len(mismatched), n_checked), **common)
            return
        self.finish(
            status, ok=status == "verified",
            message_en=f"{n_checked} of {total} numbers checked against the public archive; "
                       f"{matched} matched within {TOLERANCE}."
                       + (f" {len(unchecked)} could not be checked this time." if unchecked else ""),
            message_hi=f"{total} में से {n_checked} आँकड़े सार्वजनिक संग्रह से जाँचे गए; {matched} {TOLERANCE} के भीतर मेल खाए।"
                       + (f" {len(unchecked)} इस बार नहीं जाँचे जा सके।" if unchecked else ""),
            **common,
        )

    def _current_engine(self) -> str:
        from app.tools import geo

        return geo.ENGINE_VERSION

    def _engine_differs(self) -> bool:
        return self._current_engine() != self.core.engine_version

    def _stage(self, field_keys: set[str], checked: dict) -> None:
        done = [k for k in field_keys if k in checked]
        matched = sum(1 for k in done if checked[k]["match"])
        n = len(field_keys)
        remaining = len(self.core.numbers) - n
        if len(done) < n:
            status = "field_failed"
        elif matched < n:
            status = "field_engine_changed" if self._engine_differs() else "field_mismatch"
        else:
            status = "field_verified"
        self.emit(
            "stage_result", stage="field", status=status, matched=matched, total=n, remaining=remaining,
            message_en=f"{matched} of {n} field numbers match; {remaining} neighbourhood numbers are "
                       "still being checked.",
            message_hi=f"खेत के {n} में से {matched} आँकड़े मेल खाते हैं; आसपास के {remaining} आँकड़ों की जाँच अभी जारी है।",
        )


def _engine_changed_text(n_different: int, n_checked: int) -> dict:
    return {
        "message_en": f"This record was sealed by an earlier engine version, so numbers may legitimately "
                      f"differ: {n_different} of {n_checked} checked numbers differ. The record still "
                      "matches its seal. To compare like with like, run a new investigation.",
        "message_hi": f"यह रिकॉर्ड इंजन के पहले के संस्करण से बना था, इसलिए आँकड़े जायज़ तौर पर अलग हो सकते हैं: जाँचे गए "
                      f"{n_checked} में से {n_different} आँकड़े अलग हैं। रिकॉर्ड अपनी मुहर से अब भी मेल खाता है। बराबर की "
                      "तुलना के लिए नई जाँच चलाएँ।",
        "message_te": f"ఈ రికార్డు ఇంజిన్ పాత వెర్షన్‌తో తయారైంది, కాబట్టి సంఖ్యలు సహేతుకంగానే వేరుగా ఉండవచ్చు: తనిఖీ చేసిన "
                      f"{n_checked} సంఖ్యలలో {n_different} వేరుగా ఉన్నాయి. రికార్డు ఇప్పటికీ దాని ముద్రతో సరిపోలుతోంది. "
                      "సమానంగా పోల్చడానికి కొత్త పరిశీలన చేయండి.",
    }


def _start_job(hash_value: str, core: ReplayCore, case_id: str | None, superseded: bool,
               last_full: dict | None) -> str:
    run_id = new_id()
    with session_scope() as s:
        s.add(VerifyRun(id=run_id, evidence_hash=hash_value, status="running"))
    job = _Job(run_id, hash_value, core)
    job.emit(
        "start", hash=hash_value, hash_verified=True, case_id=case_id, superseded=superseded,
        engine_version=core.engine_version, event_date=core.event_date.isoformat(),
        optical_pre_id=core.optical_pre_id, optical_post_id=core.optical_post_id,
        sar_pre_id=core.sar_pre_id, sar_post_id=core.sar_post_id,
        history_scene_ids=core.history_scene_ids, seed=core.seed, n_numbers=len(core.numbers),
        numbers=core.numbers, tolerance=TOLERANCE, polygon=core.polygon, source=SOURCE,
        scene_archives=core.scene_archives, cached=False, last_full_check=last_full,
        started_at=datetime.now(UTC).isoformat(),
    )
    if not core.numbers:
        job.finish("nothing_to_recompute", ok=True, n_numbers=0, checked=0, total=0,
                   message_en="This record holds no satellite numbers to recompute.",
                   message_hi="इस रिकॉर्ड में दोबारा जाँचने के लिए सैटेलाइट के आँकड़े नहीं हैं।")
        return run_id
    _jobs.submit(job.run)
    return run_id


def _latest(hash_value: str, *statuses: str) -> VerifyRun | None:
    with session_scope() as s:
        query = select(VerifyRun).where(VerifyRun.evidence_hash == hash_value)
        if statuses:
            query = query.where(VerifyRun.status.in_(statuses))
        return s.scalars(query.order_by(VerifyRun.started_at.desc()).limit(1)).first()


def _summary(run: VerifyRun | None) -> dict | None:
    if run is None:
        return None
    return {"status": run.status, "checked": run.checked, "total": run.total,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None}


def _events_after(run_id: str, after: int) -> list[dict]:
    with session_scope() as s:
        return [
            row.payload for row in s.scalars(
                select(VerifyEvent).where(VerifyEvent.run_id == run_id, VerifyEvent.seq > after)
                .order_by(VerifyEvent.seq)
            ).all()
        ]


def _sse(payload: dict) -> dict:
    data = {"event": "message", "data": json.dumps(payload, ensure_ascii=False)}
    if "seq" in payload:
        data["id"] = str(payload["seq"])
    return data


def _final(status: str, **data) -> dict:
    return {"type": "result", "status": status, "ok": False, **data}


def _prepare(hash_value: str, after: int, rerun: bool) -> tuple[str | None, bool, dict | None]:
    """Returns (run to stream, whether it is a stored check, an immediate final event if any)."""
    core_json, case_id, superseded = load_core(hash_value)
    if core_json is None:
        return None, False, _final(
            "unknown_hash", message_en="No evidence record has this hash.",
            message_hi="इस हैश का कोई सबूत रिकॉर्ड नहीं मिला।",
        )
    core = ReplayCore.model_validate(core_json)
    recomputed_hash = evidence_hash(core)
    if recomputed_hash != hash_value:
        return None, False, _final(
            "tampered", stored_hash=hash_value, recomputed_hash=recomputed_hash,
            message_en="The stored record does not match its hash, so it was changed after it was sealed.",
            message_hi="रखा हुआ रिकॉर्ड अपने हैश से मेल नहीं खाता, यानी मुहर लगने के बाद इसे बदला गया है।",
        )
    from app.tools import geo

    # A number is only checked against the archive it was read from. The engine resolves each scene
    # id to its archive; a record it would now read elsewhere is reported, not silently re-pointed.
    moved = {
        sid: {"sealed": sealed, "current": geo.scene_archive(sid)}
        for sid, sealed in core.scene_archives.items()
        if geo.scene_archive(sid) != sealed
    }
    if moved:
        return None, False, _final(
            "archive_mismatch", moved=moved,
            message_en="A scene in this record would now be read from a different archive than the "
                       "one it was sealed from, so it was not recomputed.",
            message_hi="इस रिकॉर्ड की एक तस्वीर अब उस संग्रह से नहीं पढ़ी जाएगी जिससे मुहर लगी थी, इसलिए दोबारा गणना नहीं की गई।",
        )
    with _start_lock:
        running = _latest(hash_value, "running")
        if running is not None:
            return running.id, False, None
        latest = _latest(hash_value)
        if after > 0 and latest is not None:
            return latest.id, False, None  # a client coming back to a job that has since finished
        full = _latest(hash_value, "verified", "mismatch", "engine_changed", "nothing_to_recompute")
        if full is not None and not rerun:
            return full.id, True, None
        return _start_job(hash_value, core, case_id, superseded, _summary(full)), False, None


def _with_engine_status(payload: dict, run_id: str) -> dict:
    """A check finished before engine_changed existed still reads as what it was."""
    if payload.get("type") != "result" or payload.get("status") != "mismatch":
        return payload
    with session_scope() as s:
        rows = s.scalars(select(VerifyEvent).where(VerifyEvent.run_id == run_id)).all()
        differed = any((r.payload or {}).get("kind") == "engine_version_differs" for r in rows)
    if not differed:
        return payload
    text = _engine_changed_text(len(payload.get("mismatched") or []), payload.get("checked") or 0)
    return {**payload, "status": "engine_changed", **text}


def _as_stored(payload: dict, run: VerifyRun | None) -> dict:
    """A check from earlier, labelled as one on the events that frame it."""
    if payload["type"] not in ("start", "result"):
        return payload
    return {**payload, "cached": True, "checked_at": run.finished_at.isoformat() if run else None,
            "message_cached_en": "This is the last full check, with its time. Run it again to re-download now.",
            "message_cached_hi": "यह पिछली पूरी जाँच है, उसके समय के साथ। अभी दोबारा डाउनलोड करके जाँचने के लिए फिर चलाएँ।",
            "rerun": "?rerun=1"}


async def stream(hash_value: str, after: int = 0, rerun: bool = False) -> AsyncIterator[dict]:
    run_id, stored, final = await asyncio.to_thread(_prepare, hash_value, after, rerun)
    if final is not None:
        yield _sse(final)
        return
    run = await asyncio.to_thread(_latest_by_id, run_id) if stored else None
    cursor = after
    while True:
        events = await asyncio.to_thread(_events_after, run_id, cursor)
        for payload in events:
            cursor = payload["seq"]
            if stored and payload["type"] == "progress":
                continue
            if payload["type"] == "result":
                payload = await asyncio.to_thread(_with_engine_status, payload, run_id)
            yield _sse(_as_stored(payload, run) if stored else payload)
            if payload["type"] == "result":
                return
        await asyncio.sleep(POLL_S)


def _latest_by_id(run_id: str) -> VerifyRun | None:
    with session_scope() as s:
        return s.get(VerifyRun, run_id)


def recover_interrupted() -> int:
    """A restart kills running jobs. Close them, so a returning client gets an honest ending."""
    with session_scope() as s:
        rows = s.scalars(select(VerifyRun).where(VerifyRun.status == "running")).all()
        ids = [(r.id, r.evidence_hash) for r in rows]
    for run_id, hash_value in ids:
        with session_scope() as s:
            seq = s.scalar(select(func.max(VerifyEvent.seq)).where(VerifyEvent.run_id == run_id)) or 0
            rows = s.scalars(select(VerifyEvent).where(VerifyEvent.run_id == run_id,
                                                       VerifyEvent.payload.is_not(None))).all()
            numbers = [r.payload for r in rows if r.payload.get("type") == "number"]
            total = next((r.payload.get("n_numbers") for r in rows if r.payload.get("type") == "start"), None)
            s.add(VerifyEvent(run_id=run_id, seq=seq + 1, payload={
                "type": "result", "seq": seq + 1, "run_id": run_id, "status": "partial", "ok": False,
                "checked": len(numbers), "matched": sum(1 for n in numbers if n.get("match")), "total": total,
                "message_en": "The server restarted during this check. Scan again to run it again.",
                "message_hi": "जाँच के दौरान सर्वर दोबारा शुरू हुआ। फिर से जाँचने के लिए दोबारा स्कैन करें।",
            }))
            run = s.get(VerifyRun, run_id)
            run.status, run.finished_at, run.checked, run.total = "partial", utcnow(), len(numbers), total
        log.warning("closed verify run %s for %s after a restart", run_id, hash_value)
    return len(ids)

"""Verification: the hash, the live comparison, and tamper detection."""
import asyncio
import json

from app import verify
from app.agent.graph import canonical_json, evidence_hash
from app.db import EvidenceRow, session_scope
from app.evidence.schema import ReplayCore
from tests.conftest import install_fake_geo

CORE = ReplayCore(
    engine_version="test-1", polygon={"type": "Polygon", "coordinates": [[[75, 29], [75.01, 29], [75, 29.01], [75, 29]]]},
    event_date="2026-10-25", optical_pre_id="a", optical_post_id="b", seed=7,
    numbers={"optical.plot_delta_ndvi": -0.25, "neighbours.placebo.p_value": 0.02, "sar.vh_change_db": None},
)


def seed_row(core=CORE, stored_hash=None):
    h = stored_hash or evidence_hash(core)
    with session_scope() as s:
        from app.db import Case, Run

        s.add(Case(id="c1", lat=29.5, lon=75.0))
        s.add(Run(id="r1", case_id="c1"))
        s.add(EvidenceRow(run_id="r1", case_id="c1", json={}, evidence_hash=h,
                          replay_core=core.model_dump(mode="json")))
    return h


def collect(h):
    async def run():
        return [json.loads(e["data"]) async for e in verify.stream(h)]

    return asyncio.run(run())


def test_hash_is_sha256_of_sorted_canonical_json():
    import hashlib

    data = CORE.model_dump(mode="json")
    expected = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                         ensure_ascii=False).encode()).hexdigest()
    assert evidence_hash(CORE) == expected
    shuffled = dict(reversed(list(data.items())))
    assert canonical_json(shuffled) == canonical_json(data)


def test_hash_changes_with_any_number():
    changed = CORE.model_copy(update={"numbers": {**CORE.numbers, "optical.plot_delta_ndvi": -0.26}})
    assert evidence_hash(changed) != evidence_hash(CORE)


def test_unknown_hash():
    events = collect("0" * 64)
    assert events == [e for e in events if e["type"] == "result"]
    assert events[-1]["status"] == "unknown_hash" and not events[-1]["ok"]


def test_verified_stream(monkeypatch):
    install_fake_geo(monkeypatch, replay=lambda core: {**core.numbers, "optical.plot_delta_ndvi": -0.2505})
    h = seed_row()
    events = collect(h)
    assert events[0]["type"] == "start" and events[0]["hash_verified"]
    numbers = [e for e in events if e["type"] == "number"]
    assert len(numbers) == 3 and all(n["match"] for n in numbers)
    assert next(n for n in numbers if n["field"] == "optical.plot_delta_ndvi")["recomputed"] == -0.2505
    assert events[-1] == {**events[-1], "status": "verified", "ok": True, "matched": 3, "total": 3}


def test_number_outside_tolerance_is_a_mismatch(monkeypatch):
    install_fake_geo(monkeypatch, replay=lambda core: {**core.numbers, "neighbours.placebo.p_value": 0.03})
    events = collect(seed_row())
    assert events[-1]["status"] == "mismatch" and not events[-1]["ok"]
    assert events[-1]["mismatched"] == ["neighbours.placebo.p_value"]


def test_missing_recomputed_number_is_not_a_match(monkeypatch):
    install_fake_geo(monkeypatch, replay=lambda core: {"optical.plot_delta_ndvi": -0.25})
    events = collect(seed_row())
    assert events[-1]["status"] == "mismatch"


def test_tampering_with_the_stored_record_is_detected_before_any_replay(monkeypatch):
    def replay(core):
        raise AssertionError("a tampered record must not be replayed")

    install_fake_geo(monkeypatch, replay=replay)
    h = seed_row()
    with session_scope() as s:
        row = s.query(EvidenceRow).filter_by(evidence_hash=h).one()
        forged = dict(row.replay_core)
        forged["numbers"] = {**forged["numbers"], "optical.plot_delta_ndvi": -0.75}
        row.replay_core = forged
    events = collect(h)
    assert len(events) == 1 and events[0]["status"] == "tampered" and not events[0]["ok"]
    assert events[0]["recomputed_hash"] != h


def test_slow_replay_streams_progress(monkeypatch):
    import time

    def slow(core):
        time.sleep(0.2)
        return dict(core.numbers)

    monkeypatch.setattr(verify, "PROGRESS_EVERY_S", 0.05)
    install_fake_geo(monkeypatch, replay=slow)
    events = collect(seed_row())
    assert any(e["type"] == "progress" for e in events) and events[-1]["status"] == "verified"


def test_upstream_outage_is_not_reported_as_a_mismatch(monkeypatch):
    def replay(core):
        raise RuntimeError("archive down")

    install_fake_geo(monkeypatch, replay=replay)
    events = collect(seed_row())
    assert events[-1]["status"] == "upstream_unavailable" and "says nothing" in events[-1]["message_en"]


def test_start_carries_the_stored_numbers_and_the_source(monkeypatch):
    install_fake_geo(monkeypatch)
    start = collect(seed_row())[0]
    assert start["numbers"] == CORE.numbers
    assert start["source"]["read"] == "network" and "fresh=True" in start["source"]["cache"]


def _with_groups(monkeypatch, groups):
    install_fake_geo(monkeypatch, replay_groups=lambda core: groups)


def test_groups_stream_as_they_finish(monkeypatch):
    _with_groups(monkeypatch, [
        ("optical", lambda: {"optical.plot_delta_ndvi": -0.25, "neighbours.placebo.p_value": 0.02}),
        ("radar", lambda: {"sar.vh_change_db": None}),
    ])
    events = collect(seed_row())
    kinds = [e["type"] for e in events]
    assert kinds.index("group_done") < kinds.index("group_started", kinds.index("group_done"))
    assert [e["group"] for e in events if e["type"] == "number"] == ["optical", "optical", "radar"]
    assert events[-1]["status"] == "verified" and events[-1]["checked"] == 3


def test_partial_result_says_n_of_m(monkeypatch):
    def down():
        raise RuntimeError("archive slow")

    _with_groups(monkeypatch, [
        ("optical", lambda: {"optical.plot_delta_ndvi": -0.25, "neighbours.placebo.p_value": 0.02}),
        ("radar", down),
    ])
    events = collect(seed_row())
    result = events[-1]
    assert result["status"] == "partial" and not result["ok"]
    assert (result["checked"], result["total"]) == (2, 3) and result["unchecked"] == ["sar.vh_change_db"]
    assert "2 of 3 numbers checked" in result["message_en"]
    assert any(e["type"] == "group_failed" and e["group"] == "radar" for e in events)


def test_all_groups_failing_is_upstream_not_mismatch(monkeypatch):
    def down():
        raise RuntimeError("archive down")

    _with_groups(monkeypatch, [("optical", down)])
    assert collect(seed_row())[-1]["status"] == "upstream_unavailable"


def test_a_group_past_its_budget_does_not_starve_the_next(monkeypatch):
    import time

    monkeypatch.setattr(verify, "GROUP_BUDGET_S", {"optical": 0.05})
    monkeypatch.setattr(verify, "DEFAULT_BUDGET_S", 30)
    monkeypatch.setattr(verify, "PROGRESS_EVERY_S", 0.02)
    _with_groups(monkeypatch, [
        ("optical", lambda: time.sleep(1) or {"optical.plot_delta_ndvi": -0.25}),
        ("radar", lambda: {"sar.vh_change_db": None}),
    ])
    events = collect(seed_row())
    failed = next(e for e in events if e["type"] == "group_failed")
    assert failed["group"] == "optical" and "budget" in failed["reason"]
    assert failed["fields"] == ["neighbours.placebo.p_value", "optical.plot_delta_ndvi"]
    assert events[-1]["status"] == "partial" and events[-1]["checked"] == 1


def test_real_recomputations_really_read_fresh():
    """A verification that read our own cache would prove nothing, so the switch is pinned."""
    import inspect

    from app.tools.geo.optical import _optical_compare, history_from_ids
    from app.tools.geo.sar import _sar_compare
    from app.tools.geo.scale import _scale_fade
    from app.tools.geo.village import _village_witness

    for fn in (_optical_compare, _sar_compare, history_from_ids, _scale_fade, _village_witness):
        assert "fresh" in inspect.signature(fn).parameters, fn
    source = inspect.getsource(verify.default_groups)
    assert source.count("fresh=True") >= 6
    from app.tools.geo import replay_field

    assert inspect.getsource(replay_field).count("fresh=True") >= 2


def test_a_superseded_hash_stays_verifiable(monkeypatch):
    from app.db import cache_put

    install_fake_geo(monkeypatch)
    h = evidence_hash(CORE)
    cache_put(f"sealed:{h}", "superseded-seal", None, CORE.model_dump(mode="json"))
    events = collect(h)
    assert events[0]["superseded"] is True and events[-1]["status"] == "verified"


def test_start_names_each_scenes_archive(monkeypatch):
    core = CORE.model_copy(update={"scene_archives": {"a": "planetary-computer", "b": "planetary-computer"}})
    install_fake_geo(monkeypatch, scene_archive=lambda sid: "planetary-computer")
    events = collect(seed_row(core))
    assert events[0]["scene_archives"] == {"a": "planetary-computer", "b": "planetary-computer"}
    assert events[-1]["status"] == "verified"


def test_a_scene_now_resolving_to_another_archive_is_reported(monkeypatch):
    def replay(core):
        raise AssertionError("must not recompute against another archive")

    core = CORE.model_copy(update={"scene_archives": {"a": "earth-search"}})
    install_fake_geo(monkeypatch, scene_archive=lambda sid: "planetary-computer", replay=replay)
    events = collect(seed_row(core))
    assert events[-1]["status"] == "archive_mismatch"
    assert events[-1]["moved"] == {"a": {"sealed": "earth-search", "current": "planetary-computer"}}


def test_engine_version_difference_is_said(monkeypatch):
    install_fake_geo(monkeypatch, ENGINE_VERSION="test-2")
    events = collect(seed_row())
    assert any(e["type"] == "note" and e["kind"] == "engine_version_differs" for e in events)


def test_a_difference_under_another_engine_is_not_called_a_mismatch(monkeypatch):
    install_fake_geo(monkeypatch, ENGINE_VERSION="test-2",
                     replay=lambda core: {**core.numbers, "neighbours.placebo.p_value": 0.03})
    result = collect(seed_row())[-1]
    assert result["status"] == "engine_changed" and result["ok"] is False
    assert result["mismatched"] == ["neighbours.placebo.p_value"]
    assert (result["sealed_engine"], result["current_engine"]) == ("test-1", "test-2")
    assert "earlier engine version" in result["message_en"] and "legitimately" in result["message_en"]
    assert result["message_hi"] and result["message_te"] and "1 of 3" in result["message_en"]


def test_a_difference_under_the_same_engine_stays_a_mismatch(monkeypatch):
    install_fake_geo(monkeypatch, replay=lambda core: {**core.numbers, "neighbours.placebo.p_value": 0.03})
    assert collect(seed_row())[-1]["status"] == "mismatch"


def test_no_difference_under_another_engine_is_simply_verified(monkeypatch):
    install_fake_geo(monkeypatch, ENGINE_VERSION="test-2")
    result = collect(seed_row())[-1]
    assert result["status"] == "verified" and result["ok"] is True


def test_a_field_difference_under_another_engine_is_said_at_the_stage_too(monkeypatch):
    install_fake_geo(monkeypatch, ENGINE_VERSION="test-2")
    _staged(monkeypatch, ("field_post", lambda: {"optical.plot_delta_ndvi": -0.5}, verify._is_field_post), RING, RADAR)
    events = collect(seed_row())
    assert next(e for e in events if e["type"] == "stage_result")["status"] == "field_engine_changed"
    assert events[-1]["status"] == "engine_changed"


def test_an_engine_changed_check_is_kept_like_any_full_check(monkeypatch):
    calls = []
    install_fake_geo(monkeypatch, ENGINE_VERSION="test-2")
    _staged(monkeypatch, ("all", lambda: calls.append(1) or {**CORE.numbers, "optical.plot_delta_ndvi": -0.5}, lambda key: True))
    h = seed_row()
    assert collect(h)[-1]["status"] == "engine_changed"
    again = collect(h)
    assert len(calls) == 1 and again[-1]["status"] == "engine_changed" and again[-1]["cached"] is True


def test_a_mismatch_stored_before_this_status_existed_reads_as_engine_changed():
    from app.db import VerifyEvent, VerifyRun

    with session_scope() as s:
        s.add(VerifyRun(id="old", evidence_hash="h" * 64, status="mismatch"))
        s.add(VerifyEvent(run_id="old", seq=1, payload={"type": "note", "seq": 1, "kind": "engine_version_differs"}))
    stored = {"type": "result", "status": "mismatch", "mismatched": ["a"], "checked": 3}
    assert verify._with_engine_status(stored, "old")["status"] == "engine_changed"
    with session_scope() as s:
        s.add(VerifyRun(id="same", evidence_hash="i" * 64, status="mismatch"))
        s.add(VerifyEvent(run_id="same", seq=1, payload={"type": "note", "seq": 1, "kind": "source"}))
    assert verify._with_engine_status(stored, "same")["status"] == "mismatch"


def _staged(monkeypatch, *groups):
    monkeypatch.setattr(verify, "_groups_for", lambda core: [
        verify.Group(name, fn, select) for name, fn, select in groups
    ])


FIELD_CORE = ("field_post", lambda: {"optical.plot_delta_ndvi": -0.25}, verify._is_field_post)
RING = ("ring", lambda: {"neighbours.placebo.p_value": 0.02}, verify._is_ring)
RADAR = ("radar", lambda: {"sar.vh_change_db": None}, lambda key: key.startswith("sar."))


def _down():
    raise RuntimeError("archive slow")


def test_field_stage_reports_first_with_the_honest_remainder(monkeypatch):
    install_fake_geo(monkeypatch)
    _staged(monkeypatch, FIELD_CORE, RING, RADAR)
    events = collect(seed_row())
    kinds = [e["type"] for e in events]
    stage = next(e for e in events if e["type"] == "stage_result")
    assert kinds.index("stage_result") < kinds.index("group_started", kinds.index("stage_result"))
    assert stage["status"] == "field_verified"
    assert "1 of 1 field numbers match; 2 neighbourhood numbers are still being checked" in stage["message_en"]
    assert events[-1]["status"] == "verified" and events[-1]["ok"] is True


def test_field_only_is_never_called_verified_overall(monkeypatch):
    install_fake_geo(monkeypatch)
    _staged(monkeypatch, FIELD_CORE, ("ring", _down, verify._is_ring), ("radar", _down, RADAR[2]))
    result = collect(seed_row())[-1]
    assert result["status"] == "field_verified" and result["ok"] is False and result["field_verified"]
    assert result["unchecked"] == ["neighbours.placebo.p_value", "sar.vh_change_db"]
    assert set(result["errors"]) == {"ring", "radar"}


def test_field_mismatch_is_said_at_once_and_at_the_end(monkeypatch):
    install_fake_geo(monkeypatch)
    _staged(monkeypatch, ("field_post", lambda: {"optical.plot_delta_ndvi": -0.5}, verify._is_field_post), RING, RADAR)
    events = collect(seed_row())
    assert next(e for e in events if e["type"] == "stage_result")["status"] == "field_mismatch"
    assert events[-1]["status"] == "mismatch" and events[-1]["mismatched"] == ["optical.plot_delta_ndvi"]


def test_field_failure_does_not_stop_the_neighbourhood(monkeypatch):
    install_fake_geo(monkeypatch)
    _staged(monkeypatch, ("field_post", _down, verify._is_field_post), RING, RADAR)
    events = collect(seed_row())
    assert next(e for e in events if e["type"] == "stage_result")["status"] == "field_failed"
    assert events[-1]["status"] == "partial" and events[-1]["checked"] == 2


def test_no_number_is_counted_twice(monkeypatch):
    install_fake_geo(monkeypatch)
    everything = lambda key: True
    _staged(monkeypatch, FIELD_CORE, ("a", lambda: dict(CORE.numbers), everything),
            ("b", lambda: dict(CORE.numbers), everything))
    events = collect(seed_row())
    assert len([e for e in events if e["type"] == "number"]) == 3
    assert events[-1]["checked"] == 3 and events[-1]["total"] == 3


def test_leaving_and_returning_with_after(monkeypatch):
    import threading

    release = threading.Event()
    install_fake_geo(monkeypatch)
    _staged(monkeypatch, FIELD_CORE, ("ring", lambda: release.wait(20) and RING[1](), verify._is_ring), RADAR)
    h = seed_row()

    async def first_part():
        out = []
        async for e in verify.stream(h):
            out.append(json.loads(e["data"]))
            if out[-1]["type"] == "stage_result":
                break
        return out

    seen = asyncio.run(first_part())
    assert seen[0]["seq"] == 1 and seen[-1]["type"] == "stage_result"
    release.set()  # the job carries on with no client attached

    async def rest():
        return [json.loads(e["data"]) async for e in verify.stream(h, after=seen[-1]["seq"])]

    remainder = asyncio.run(rest())
    assert remainder[0]["seq"] == seen[-1]["seq"] + 1
    assert [e["seq"] for e in remainder] == list(range(remainder[0]["seq"], remainder[-1]["seq"] + 1))
    assert remainder[-1]["status"] == "verified"
    from app.db import VerifyRun

    with session_scope() as s:
        assert s.query(VerifyRun).count() == 1


def test_repeat_scan_shows_the_stored_check_labelled_and_can_rerun(monkeypatch):
    calls = []
    install_fake_geo(monkeypatch)
    _staged(monkeypatch, ("all", lambda: calls.append(1) or dict(CORE.numbers), lambda key: True))
    h = seed_row()
    assert collect(h)[-1]["status"] == "verified" and len(calls) == 1
    again = collect(h)
    assert len(calls) == 1, "a fully checked record is not downloaded again without asking"
    assert again[0]["cached"] is True and again[-1]["cached"] is True
    assert again[-1]["checked_at"] and again[-1]["rerun"] == "?rerun=1"
    assert "last full check" in again[-1]["message_cached_en"]

    async def rerun():
        return [json.loads(e["data"]) async for e in verify.stream(h, rerun=True)]

    fresh = asyncio.run(rerun())
    assert len(calls) == 2 and fresh[0]["cached"] is False
    assert fresh[0]["last_full_check"]["status"] == "verified"
    assert fresh[-1].get("cached") is None


def test_a_repeat_scan_after_a_partial_check_tries_again(monkeypatch):
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("archive slow")
        return dict(CORE.numbers)

    install_fake_geo(monkeypatch)
    _staged(monkeypatch, ("all", flaky, lambda key: True))
    h = seed_row()
    assert collect(h)[-1]["status"] == "upstream_unavailable"
    assert collect(h)[-1]["status"] == "verified"


def test_two_scans_share_one_job(monkeypatch):
    import threading

    release = threading.Event()
    calls = []

    def slow():
        calls.append(1)
        release.wait(20)
        return dict(CORE.numbers)

    install_fake_geo(monkeypatch)
    _staged(monkeypatch, ("all", slow, lambda key: True))
    h = seed_row()

    async def both():
        async def one():
            return [json.loads(e["data"]) async for e in verify.stream(h)]

        tasks = [asyncio.create_task(one()), asyncio.create_task(one())]
        await asyncio.sleep(0.6)
        release.set()
        return await asyncio.gather(*tasks)

    first, second = asyncio.run(both())
    assert len(calls) == 1 and first[-1]["status"] == second[-1]["status"] == "verified"


def test_restart_closes_a_running_check_honestly():
    from app.db import VerifyEvent, VerifyRun

    with session_scope() as s:
        s.add(VerifyRun(id="v1", evidence_hash="h" * 64, status="running"))
        s.add(VerifyEvent(run_id="v1", seq=1, payload={"type": "start", "seq": 1, "n_numbers": 5}))
        s.add(VerifyEvent(run_id="v1", seq=2, payload={"type": "number", "seq": 2, "match": True}))
    assert verify.recover_interrupted() == 1
    with session_scope() as s:
        assert s.get(VerifyRun, "v1").status == "partial"
        last = s.query(VerifyEvent).filter_by(run_id="v1", seq=3).one().payload
    assert last["type"] == "result" and last["checked"] == 1 and last["total"] == 5 and not last["ok"]
    assert "restarted" in last["message_en"]


def test_real_groups_cover_every_sealed_key_once():
    """Every key the engine can seal belongs to exactly one real group, so none goes unchecked."""
    from app.evidence.schema import (
        NeighbourEvidence,
        OpticalEvidence,
        SarEvidence,
    )
    from app.tools.geo.replay import flatten_numbers
    from tests.conftest import placebo, stats

    keys = flatten_numbers(
        OpticalEvidence(pre=stats("a", CORE.event_date, 0.5), post=stats("b", CORE.event_date, 0.4),
                        plot_delta_ndvi=-0.1, drop_frac=0.1, iqr_delta=0.1, post_bare_fraction=0.1),
        NeighbourEvidence(n_comparable_pixels=1, neighbour_median_delta=0.0, plot_minus_neighbour=0.0,
                          placebo=placebo(), far_placebo=placebo(), pretrend_delta=0.0,
                          pretrend_placebo=placebo()),
        SarEvidence(usable=True, placebo=placebo()),
    )
    selectors = [verify._is_field_pre, verify._is_field_post, verify._is_field_extra, lambda k: k in verify._SAR_FIELD_KEYS,
                 verify._is_ring, verify._is_far_twin, verify._is_radar]
    for key in keys:
        assert sum(1 for select in selectors if select(key)) == 1, key


def test_a_job_empties_gdals_http_cache_and_says_so(monkeypatch):
    install_fake_geo(monkeypatch)
    calls = []
    monkeypatch.setattr(verify, "clear_http_cache", lambda: calls.append(1) or True)
    _staged(monkeypatch, RADAR)
    events = collect(seed_row())
    note = next(e for e in events if e["type"] == "note" and e["kind"] == "source")
    assert calls == [1] and note["http_cache_cleared"] is True


def test_gdals_http_cache_can_really_be_emptied():
    assert verify.clear_http_cache() is True


def _recording_session(log):
    from contextlib import contextmanager

    @contextmanager
    def fresh_session():
        log.append("enter")
        try:
            yield
        finally:
            log.append("exit")

    return fresh_session


def test_a_check_runs_all_its_groups_inside_one_fresh_session(monkeypatch):
    log = []
    install_fake_geo(monkeypatch, fresh_session=_recording_session(log))
    _staged(monkeypatch, ("field_post", lambda: log.append("field") or {"optical.plot_delta_ndvi": -0.25}, verify._is_field_post),
            ("ring", lambda: log.append("ring") or {"neighbours.placebo.p_value": 0.02}, verify._is_ring), RADAR)
    events = collect(seed_row())
    assert log == ["enter", "field", "ring", "exit"]
    assert events[-1]["status"] == "verified"
    note = next(e for e in events if e["type"] == "note" and e["kind"] == "source")
    assert note["source"]["read"] == "network" and "fresh=True" in note["source"]["cache"]
    assert "reused within it" in note["source"]["session"]


def test_the_session_ends_when_a_check_fails(monkeypatch):
    log = []
    install_fake_geo(monkeypatch, fresh_session=_recording_session(log))
    monkeypatch.setattr(verify, "_groups_for", lambda core: 1 / 0)
    assert collect(seed_row())[-1]["status"] == "partial"
    assert log == ["enter", "exit"]


def test_a_stored_check_opens_no_session(monkeypatch):
    log = []
    install_fake_geo(monkeypatch, fresh_session=_recording_session(log))
    h = seed_row()
    collect(h)
    assert log.count("enter") == 1
    collect(h)
    assert log.count("enter") == 1


def test_the_engine_exports_the_session():
    from app.tools import geo

    with geo.fresh_session():
        pass

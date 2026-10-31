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


def test_a_group_past_the_time_limit_is_partial(monkeypatch):
    import time

    monkeypatch.setattr(verify, "REPLAY_TIMEOUT_S", 0.05)
    monkeypatch.setattr(verify, "PROGRESS_EVERY_S", 0.02)
    _with_groups(monkeypatch, [
        ("optical", lambda: {"optical.plot_delta_ndvi": -0.25, "neighbours.placebo.p_value": 0.02}),
        ("radar", lambda: time.sleep(1) or {"sar.vh_change_db": None}),
    ])
    result = collect(seed_row())[-1]
    assert result["status"] == "partial" and result["checked"] == 2


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
    assert source.count("fresh=True") >= 5


def test_a_superseded_hash_stays_verifiable(monkeypatch):
    from app.db import cache_put

    install_fake_geo(monkeypatch)
    h = evidence_hash(CORE)
    cache_put(f"sealed:{h}", "superseded-seal", None, CORE.model_dump(mode="json"))
    events = collect(h)
    assert events[0]["superseded"] is True and events[-1]["status"] == "verified"


def test_engine_version_difference_is_said(monkeypatch):
    install_fake_geo(monkeypatch, ENGINE_VERSION="test-2")
    events = collect(seed_row())
    assert any(e["type"] == "note" and e["kind"] == "engine_version_differs" for e in events)

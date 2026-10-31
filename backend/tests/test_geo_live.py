"""Live checks against the real archives. Run with: uv run pytest -m live tests/test_geo_live.py"""
from __future__ import annotations

import math
from datetime import date

import pytest

from app.tools.geo import (
    PlotError,
    flatten_numbers,
    optical_compare,
    qa_scene,
    replay,
    sar_compare,
    search_optical,
    search_sar,
)
from app.evidence.schema import ReplayCore

pytestmark = pytest.mark.live


def square(lon: float, lat: float, side_m: float = 120.0) -> dict:
    dlat = side_m / 2 / 111_320
    dlon = dlat / math.cos(math.radians(lat))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]
    return {"type": "Polygon", "coordinates": [ring]}


SIRSA = square(75.03, 29.53)


def test_28_oct_2026_is_rejected_despite_clean_metadata():
    scenes = search_optical(SIRSA, date(2026, 10, 28), date(2026, 10, 28))
    assert scenes, "the 28 Oct 2026 pass should exist over Sirsa"
    for scene in scenes:
        assert scene.cloud_pct < 1, "this regression only means something while metadata looks clean"
        qa = qa_scene(scene, SIRSA)
        assert qa.status == "rejected"
        assert any(r.startswith("Q3") or r.startswith("Q4") for r in qa.reasons)


def test_clean_pass_is_accepted_with_the_offset_read_from_the_item():
    scenes = search_optical(SIRSA, date(2026, 10, 18), date(2026, 10, 18))
    assert scenes and scenes[0].processing_baseline >= "04.00"
    assert qa_scene(scenes[0], SIRSA).status == "accepted"


def test_ocean_polygon_is_a_clear_error():
    with pytest.raises(PlotError, match="coverage"):
        search_optical(square(70.0, -35.0), date(2026, 10, 1), date(2026, 10, 10))


def test_utm_44_scene_search_works_for_coastal_andhra():
    scenes = search_optical(square(81.8, 16.6), date(2026, 10, 10), date(2026, 10, 12))
    assert scenes and all(s.epsg == 32644 for s in scenes)


def test_different_orbits_are_refused():
    scenes = search_sar(SIRSA, date(2026, 10, 10), date(2026, 10, 31))
    asc = next(s for s in scenes if s.orbit_state == "ascending")
    desc = next(s for s in scenes if s.orbit_state == "descending")
    first, second = sorted((asc, desc), key=lambda s: s.datetime)
    result = sar_compare(SIRSA, first.id, second.id, seed=1)
    assert result.usable is False and "orbit" in result.reason


def test_two_runs_and_a_replay_give_identical_numbers():
    pre = search_optical(SIRSA, date(2026, 10, 13), date(2026, 10, 13))[0].id
    post = search_optical(SIRSA, date(2026, 10, 18), date(2026, 10, 18))[0].id
    a = flatten_numbers(*optical_compare(SIRSA, pre, post, seed=7))
    b = flatten_numbers(*optical_compare(SIRSA, pre, post, seed=7))
    assert a == b
    core = ReplayCore(
        engine_version="test", polygon=SIRSA, event_date=date(2026, 10, 15),
        optical_pre_id=pre, optical_post_id=post, seed=7, numbers=a,
    )
    assert replay(core) == a

"""The field replay against the full engine, on one real window recorded from the public archive.

The recording covers more than the plot. The full engine's functions see all of it, the field replay
sees only its own small window, and the numbers have to be identical.
"""
import json
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest

from app.evidence.schema import OpticalEvidence
from app.tools.geo import indices as ix
from app.tools.geo import optical, replay_field
from app.tools.geo.base import RED_EDGE_MIN_HA, S2_COLLECTION, SceneRef, r4
from app.tools.geo.grid import Grid, parse_plot
from app.tools.geo.replay import flatten_numbers

FIXTURE = Path(__file__).parent / "fixtures" / "field_window.npz"


@pytest.fixture
def window(monkeypatch):
    """Serves reads from the recording, cropped to whatever grid is asked for."""
    data = np.load(FIXTURE)
    meta = json.loads(str(data["meta"]))
    epsg, left, top, width, height = meta["grid"]
    big = Grid(int(epsg), left, top, int(width), int(height))
    plot = parse_plot(meta["polygon"])
    roles = {meta["pre_id"]: "pre", meta["post_id"]: "post"}
    arrays = {k: data[k].copy() for k in data.files if k != "meta"}

    def crop(arr, grid):
        col, row = int((grid.left - big.left) / 10), int((big.top - grid.top) / 10)
        assert col >= 0 and row >= 0 and col + grid.width <= big.width and row + grid.height <= big.height
        return arr[row: row + grid.height, col: col + grid.width].copy()

    def read_many(requests, grid, *, is_float=False, fresh=False):
        assert fresh or grid == big, "the field replay must always read fresh"
        out = {}
        for scene_id, asset in requests:
            out.setdefault(scene_id, {})[asset] = crop(arrays[f"{roles[scene_id]}_{asset}"], grid)
        return out

    def read_assets(scene_id, assets, grid, *, is_float=False, fresh=False):
        return read_many([(scene_id, a) for a in assets], grid, is_float=is_float, fresh=True)[scene_id]

    def scene(scene_id, plot=None):
        m = meta[roles[scene_id]]
        return SceneRef(
            id=scene_id, collection=S2_COLLECTION, date=date.fromisoformat(m["date"]),
            datetime=datetime.fromisoformat(m["datetime"]), processing_baseline=m["baseline"],
            boa_offset_applied=m["boa"],
        )

    monkeypatch.setattr(replay_field, "read_many", read_many)
    monkeypatch.setattr(replay_field, "get_scene", scene)
    monkeypatch.setattr(optical, "read_assets", read_assets)
    return {"meta": meta, "plot": plot, "big": big, "arrays": arrays, "scene": scene}


def full_engine(w) -> dict:
    """The full engine's own functions, on the wider window it uses for these numbers."""
    plot, grid = w["plot"], w["big"]
    mask = plot.stats_mask(grid)
    red_edge = plot.area_ha >= RED_EDGE_MIN_HA
    pre_a = optical._load_scene(w["scene"](w["meta"]["pre_id"]), grid, post=False, red_edge=red_edge, fresh=True)
    post_a = optical._load_scene(w["scene"](w["meta"]["post_id"]), grid, post=True, red_edge=red_edge, fresh=True)
    pair = mask & pre_a.valid & post_a.valid
    delta, drop_frac, iqr = ix.delta_summary((post_a.ndvi - pre_a.ndvi)[pair])
    bare = ix.bare_fraction(post_a.ndvi[mask & post_a.valid], post_a.bsi[mask & post_a.valid])
    evidence = OpticalEvidence(
        pre=optical._plot_stats(pre_a, mask), post=optical._plot_stats(post_a, mask),
        plot_delta_ndvi=r4(delta), drop_frac=r4(drop_frac), iqr_delta=r4(iqr), post_bare_fraction=r4(bare),
    )
    return flatten_numbers(evidence)


def field_replay(w) -> dict:
    replay = replay_field.FieldReplay(w["meta"]["polygon"], w["meta"]["pre_id"], w["meta"]["post_id"])
    return {**replay.core(), **replay.extra()}


def test_numbers_match_the_full_engine_exactly(window):
    full = full_engine(window)
    replayed = field_replay(window)
    assert set(replayed) == set(full)
    assert replayed == full


def test_the_window_really_is_smaller_than_the_engines(window):
    replay = replay_field.FieldReplay(window["meta"]["polygon"], window["meta"]["pre_id"], window["meta"]["post_id"])
    assert replay.grid.width * replay.grid.height < window["big"].width * window["big"].height / 4


def _put_cloud_outside_plot(window, distance_px):
    """A cloud just beyond the plot's edge, in the post scene. SCL 9 is high-probability cloud."""
    plot, big = window["plot"], window["big"]
    mask = plot.stats_mask(big)
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    row = rows.max() + 1 + distance_px
    window["arrays"]["post_SCL"][row, cols.min():cols.max() + 1] = 9
    return (rows, cols)


def test_a_cloud_next_to_the_plot_masks_the_same_pixels_in_both(window):
    clean = field_replay(window)
    _put_cloud_outside_plot(window, 1)
    full = full_engine(window)
    assert field_replay(window) == full
    assert full["optical.post.n_pixels"] < clean["optical.post.n_pixels"], "the cloud must have mattered"


def test_a_cloud_beyond_the_dilation_reach_changes_nothing(window):
    clean = field_replay(window)
    _put_cloud_outside_plot(window, ix.CLOUD_BUFFER_PX + 2)
    assert field_replay(window) == full_engine(window) == clean


def test_steps_can_run_in_order_and_each_reads_only_what_it_needs(window):
    replay = replay_field.FieldReplay(window["meta"]["polygon"], window["meta"]["pre_id"], window["meta"]["post_id"])
    pre = replay.pre_stats()
    assert all(k.startswith("optical.pre.") for k in pre) and len(pre) == 5
    assert replay.post.id not in replay.vi
    post = replay.post_stats()
    assert {"optical.post.ndvi_median", "optical.plot_delta_ndvi"} <= set(post)
    assert {**pre, **post, **replay.extra()} == full_engine(window)


def test_core_alone_gives_the_ndvi_numbers(window):
    replay = replay_field.FieldReplay(window["meta"]["polygon"], window["meta"]["pre_id"], window["meta"]["post_id"])
    core = replay.core()
    full = full_engine(window)
    assert "optical.plot_delta_ndvi" in core and "optical.post_bare_fraction" not in core
    assert all(core[k] == full[k] for k in core)

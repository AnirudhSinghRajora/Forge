"""Sentinel-2 search, plot statistics, the optical comparison, history and the timeline."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date, timedelta

import numpy as np

from app.evidence.schema import (
    HistoryEvidence,
    HistoryYear,
    NeighbourEvidence,
    OpticalEvidence,
    PlaceboTest,
    PlotStats,
    SceneQA,
    TimelinePoint,
)

from . import indices as ix
from .base import (
    RED_EDGE_MIN_HA,
    RING_M,
    S1_COLLECTION,
    S2_COLLECTION,
    PlotError,
    SceneRef,
    SceneUnusable,
    r4,
)
from .grid import Grid, Plot, parse_plot
from .far import far_placements
from .placebo import MIN_PLACEBOS, build_placebo_fields, sample_placements
from .qa import PLOT_VALID_MIN, apply_q5, plot_clear_share, qa_chain, qa_one, raw_qa, to_scene_qa
from .raster import read_assets, read_many
from .stac import get_scene, search_scenes
from .twin import field_twin

PRE_NDVI_TOLERANCE = 0.15
PRE_SPREAD_TOLERANCE = 0.05  # placebos must match the plot's pre-event NDVI IQR within this
RING_OUTERS_M = (RING_M[1], 3000)  # widen only when the 1.5 km ring has too few placements
TWIN_PRE_DAYS = 30
TWIN_MAX_PRE_SCENES = 4
TWIN_MAX_TILE_CLOUD = 60.0
PRE_WINDOW_DAYS = 25
POST_WINDOW_DAYS = 20
HISTORY_DOWNWEIGHT = 0.2
STAT_BANDS = ["B02", "B04", "B08", "B11", "SCL"]
RED_EDGE_BANDS = ["B05", "B8A"]


@dataclass(frozen=True)
class SceneArrays:
    """Reflectance-derived arrays for one scene on one grid."""

    scene: SceneRef
    ndvi: np.ndarray  # NaN where the pixel is not valid for this role
    bsi: np.ndarray
    valid: np.ndarray
    ndre: np.ndarray | None = None
    ndmi: np.ndarray | None = None


def _offset(scene: SceneRef) -> int:
    try:
        return ix.scene_offset(scene.processing_baseline, scene.boa_offset_applied)
    except ValueError as exc:
        raise SceneUnusable(f"{scene.id}: {exc}") from exc


def _load_scene(scene: SceneRef, grid: Grid, *, post: bool, red_edge: bool, fresh: bool = False) -> SceneArrays:
    names = STAT_BANDS + (RED_EDGE_BANDS if red_edge else [])
    bands = read_assets(scene.id, names, grid, fresh=fresh)
    for name in STAT_BANDS:
        if bands.get(name) is None:
            raise SceneUnusable(f"{scene.id}: band {name} is missing or unreadable")
    offset = _offset(scene)
    refl = {n: ix.to_reflectance(bands[n], offset) for n in names if n != "SCL" and bands.get(n) is not None}
    valid = ix.clear_mask(bands["SCL"], allow_water=post)
    vi = ix.ndvi(refl["B08"], refl["B04"])
    vi[~valid] = np.nan
    valid = valid & np.isfinite(vi)
    ndre = ndmi = None
    if red_edge and "B05" in refl and "B8A" in refl:
        ndre = ix.normalised_difference(refl["B8A"], refl["B05"])
        ndmi = ix.normalised_difference(refl["B8A"], refl["B11"])
    return SceneArrays(scene, vi, ix.bsi(refl["B11"], refl["B04"], refl["B08"], refl["B02"]), valid, ndre, ndmi)


def _median(values: np.ndarray) -> float | None:
    values = values[np.isfinite(values)]
    return float(np.median(values)) if values.size else None


def _plot_stats(arrays: SceneArrays, mask: np.ndarray) -> PlotStats:
    pick = mask & arrays.valid
    n = int(pick.sum())
    if n == 0:
        raise SceneUnusable(f"{arrays.scene.id}: no valid pixels inside the plot")
    vi = arrays.ndvi[pick]
    p25, p50, p75 = np.percentile(vi, [25, 50, 75])
    return PlotStats(
        scene_id=arrays.scene.id,
        date=arrays.scene.date,
        valid_frac=r4(n / mask.sum()),
        n_pixels=n,
        ndvi_median=r4(p50),
        ndvi_p25=r4(p25),
        ndvi_p75=r4(p75),
        bsi_median=r4(_median(arrays.bsi[pick])),
        ndmi_median=r4(_median(arrays.ndmi[pick])) if arrays.ndmi is not None else None,
        ndre_median=r4(_median(arrays.ndre[pick])) if arrays.ndre is not None else None,
    )


def search_optical(polygon: dict, start: Date, end: Date) -> list[SceneRef]:
    """Sentinel-2 passes over the plot in [start, end], one per pass, oldest first."""
    return search_scenes(S2_COLLECTION, parse_plot(polygon), start, end)


def qa_scene(scene: SceneRef, polygon: dict, previous_accepted: SceneQA | None = None) -> SceneQA:
    """Q1-Q5 for one scene. Works for both collections; Q5 uses `previous_accepted` if given."""
    return qa_one(scene, parse_plot(polygon), previous_accepted)


def search_and_qa(polygon: dict, start: Date, end: Date) -> list[tuple[SceneRef, SceneQA]]:
    """Optical search plus QA in date order, with Q5 chained on the last accepted scene."""
    plot = parse_plot(polygon)
    scenes = sorted(search_scenes(S2_COLLECTION, plot, start, end), key=lambda s: (s.datetime, s.id))
    return list(zip(scenes, qa_chain(scenes, plot)))


def _require_usable(qa: SceneQA) -> None:
    if qa.status == "rejected":
        raise SceneUnusable(f"scene {qa.id} was rejected by QA: {'; '.join(qa.reasons)}")


def _neighbour_stats(
    plot: Plot,
    grid: Grid,
    mask: np.ndarray,
    pre: SceneArrays,
    post: SceneArrays,
    plot_pre_median: float,
    plot_delta: float,
    seed: int,
    outer_m: int,
) -> tuple[NeighbourEvidence, np.ndarray]:
    dist = plot.distance_m(grid)
    ring = (dist >= RING_M[0]) & (dist <= outer_m)
    both = pre.valid & post.valid
    delta = post.ndvi - pre.ndvi
    comparable = ring & both & (np.abs(pre.ndvi - plot_pre_median) <= PRE_NDVI_TOLERANCE)
    n_comparable = int(comparable.sum())
    neighbour_median = _median(delta[comparable])
    bare = ix.bare_fraction(post.ndvi[comparable], post.bsi[comparable]) if n_comparable else None

    q25, q75 = np.percentile(pre.ndvi[mask & both], [25, 75])
    placements = sample_placements(
        mask, ring, both, pre.ndvi, delta, plot_pre_median, seed, PRE_NDVI_TOLERANCE,
        plot_pre_iqr=float(q75 - q25), spread_tolerance=PRE_SPREAD_TOLERANCE,
    )
    placebo = PlaceboTest(**build_placebo_fields(placements, plot_delta, "median_delta_ndvi", seed))
    evidence = NeighbourEvidence(
        ring_m=(RING_M[0], outer_m),
        n_comparable_pixels=n_comparable,
        neighbour_median_delta=r4(neighbour_median),
        plot_minus_neighbour=r4(plot_delta - neighbour_median) if neighbour_median is not None else None,
        neighbour_bare_fraction_post=r4(bare),
        placebo=placebo,
    )
    return evidence, ring


def _twin_scenes(plot: Plot, grid: Grid, mask: np.ndarray, pre: SceneRef, post: SceneRef, fresh: bool) -> list[SceneRef]:
    """Pre and post, plus clear passes in the window, keeping the newest few pre-event ones.

    Selection uses only tile-level cloud metadata and the SCL over the plot, never NDVI, so it
    cannot select on the outcome being tested.
    """
    found = search_scenes(S2_COLLECTION, plot, pre.date - timedelta(days=TWIN_PRE_DAYS), post.date)
    others = [
        s for s in found
        if s.date not in (pre.date, post.date) and (s.cloud_pct is None or s.cloud_pct <= TWIN_MAX_TILE_CLOUD)
    ]
    # Newest first, stopping once enough clear scenes are found: each SCL read costs real time.
    before = sorted((s for s in others if s.date < pre.date), key=lambda s: s.datetime, reverse=True)
    between = [s for s in others if pre.date < s.date < post.date]
    chosen = list(between)
    wanted = TWIN_MAX_PRE_SCENES - 1
    kept = 0
    for scene in before:
        if kept >= wanted:
            break
        scl = read_assets(scene.id, ["SCL"], grid, fresh=fresh)["SCL"]
        if scl is not None and plot_clear_share(scl, mask) >= PLOT_VALID_MIN:
            chosen.append(scene)
            kept += 1
    return sorted(chosen, key=lambda s: (s.datetime, s.id))


def _twin(plot: Plot, grid: Grid, mask: np.ndarray, ring: np.ndarray, pre: SceneRef, post: SceneRef, pre_qa: SceneQA, post_qa: SceneQA, fresh: bool):
    """Build the field twin and return it with the QA of every scene in its window."""
    extra = _twin_scenes(plot, grid, mask, pre, post, fresh)
    extra_qa = qa_chain(extra, plot, fresh=fresh, lite=True)
    status = {q.id: q.status for q in extra_qa}
    used = sorted([s for s in extra if status[s.id] == "accepted"] + [pre, post], key=lambda s: (s.datetime, s.id))
    bands = read_many([(s.id, b) for s in used for b in ("B04", "B08", "SCL")], grid, fresh=fresh)
    layers = []
    for s in used:
        b = bands[s.id]
        if b["B04"] is None or b["B08"] is None or b["SCL"] is None:
            raise SceneUnusable(f"{s.id}: bands needed for the field twin are missing")
        offset = _offset(s)
        vi = ix.ndvi(ix.to_reflectance(b["B08"], offset), ix.to_reflectance(b["B04"], offset))
        vi[~ix.clear_mask(b["SCL"], allow_water=s.date > pre.date)] = np.nan
        layers.append(vi)
    dates = [s.date for s in used]
    n_pre = sum(1 for s in used if s.date <= pre.date)
    stack = np.stack(layers)
    twin = field_twin(stack, dates, n_pre, dates.index(post.date), mask, ring)
    chain = sorted(extra_qa + [pre_qa, post_qa], key=lambda q: (q.date, q.id))
    return twin, chain, stack, dates


def _pretrend(
    neighbours: NeighbourEvidence, stack: np.ndarray, dates: list[Date], pre_date: Date,
    mask: np.ndarray, ring: np.ndarray, seed: int,
) -> None:
    """The same statistic on the last accepted pre-event pair: was this field already falling?

    Uses only arrays the twin already loaded, so it costs no reads. Stays None if there is no such pair.
    """
    earlier = [i for i, d in enumerate(dates) if d < pre_date]
    if not earlier or pre_date not in dates:
        return
    a, b = stack[earlier[-1]], stack[dates.index(pre_date)]
    both = np.isfinite(a) & np.isfinite(b)
    pair = mask & both
    if not pair.any():
        return
    plot_pre = float(np.median(a[mask & np.isfinite(a)]))
    value = float(np.median((b - a)[pair]))
    q25, q75 = np.percentile(a[pair], [25, 75])
    placements = sample_placements(
        mask, ring, both, a, np.nan_to_num(b - a), plot_pre, seed, PRE_NDVI_TOLERANCE,
        plot_pre_iqr=float(q75 - q25), spread_tolerance=PRE_SPREAD_TOLERANCE,
    )
    neighbours.pretrend_delta = r4(value)
    neighbours.pretrend_placebo = PlaceboTest(**build_placebo_fields(placements, value, "median_delta_ndvi", seed))


def _far_test(
    plot: Plot, mask: np.ndarray, pre: SceneRef, post: SceneRef, pre_a: SceneArrays, plot_delta: float,
    seed: int, fresh: bool,
) -> PlaceboTest:
    def layer(scene: SceneRef, bands: dict, is_post: bool):
        if bands["B04"] is None or bands["B08"] is None or bands["SCL"] is None:
            return None, None
        offset = _offset(scene)
        vi = ix.ndvi(ix.to_reflectance(bands["B08"], offset), ix.to_reflectance(bands["B04"], offset))
        vi[~ix.clear_mask(bands["SCL"], allow_water=is_post)] = np.nan
        return vi, np.isfinite(vi)

    values = pre_a.ndvi[mask & pre_a.valid]
    q25, q50, q75 = np.percentile(values, [25, 50, 75])
    placements = far_placements(
        plot, mask, pre, post, layer, float(q50), float(q75 - q25), PRE_NDVI_TOLERANCE, PRE_SPREAD_TOLERANCE, seed, fresh,
    )
    return PlaceboTest(**build_placebo_fields(placements, plot_delta, "median_delta_ndvi", seed))


def _optical_compare(
    polygon: dict, pre_id: str, post_id: str, seed: int, *, fresh: bool = False, with_twin: bool = True,
    with_far: bool = True,
) -> tuple[OpticalEvidence, NeighbourEvidence]:
    plot = parse_plot(polygon)
    pre = get_scene(pre_id, plot)
    post = get_scene(post_id, plot)
    if pre.collection != S2_COLLECTION or post.collection != S2_COLLECTION:
        raise SceneUnusable("optical_compare needs two Sentinel-2 scenes")
    if pre.datetime >= post.datetime:
        raise SceneUnusable(f"the pre scene ({pre.date}) must be earlier than the post scene ({post.date})")

    pre_qa = qa_one(pre, plot, fresh=fresh)
    post_qa = to_scene_qa(post, apply_q5(raw_qa(post, plot, fresh=fresh), post.date, pre_qa))
    _require_usable(pre_qa)
    _require_usable(post_qa)
    if pre.tile != post.tile:
        # The same pass can read about 0.1 NDVI apart in two overlapping tiles, measured at Anaparthi.
        post_qa.reasons.append(
            f"pre scene is from tile {pre.tile} and post from {post.tile}; overlapping tiles are corrected "
            "separately, so part of the change could come from that"
        )

    red_edge = plot.area_ha >= RED_EDGE_MIN_HA
    neighbours: NeighbourEvidence | None = None
    ring: np.ndarray | None = None
    for outer in RING_OUTERS_M:
        # The window has to reach the ring's outer edge; the first pass reuses the QA reads.
        grid = plot.grid(max(outer, 1500))
        mask = plot.stats_mask(grid)
        pre_a = _load_scene(pre, grid, post=False, red_edge=red_edge, fresh=fresh)
        post_a = _load_scene(post, grid, post=True, red_edge=red_edge, fresh=fresh)
        pre_stats = _plot_stats(pre_a, mask)
        post_stats = _plot_stats(post_a, mask)
        pair = mask & pre_a.valid & post_a.valid
        if not pair.any():
            raise SceneUnusable("the plot has no pixel that is valid in both scenes")
        d = (post_a.ndvi - pre_a.ndvi)[pair]
        plot_delta, drop_frac, iqr_delta = ix.delta_summary(d)
        neighbours, ring = _neighbour_stats(
            plot, grid, mask, pre_a, post_a, float(np.median(pre_a.ndvi[mask & pre_a.valid])), plot_delta, seed, outer
        )
        if neighbours.placebo is not None and neighbours.placebo.n_placebos >= MIN_PLACEBOS:
            break

    bare = ix.bare_fraction(post_a.ndvi[mask & post_a.valid], post_a.bsi[mask & post_a.valid])
    twin_grid = plot.grid()
    twin_mask = plot.stats_mask(twin_grid)
    dist = plot.distance_m(twin_grid)
    twin_ring = (dist >= RING_M[0]) & (dist <= RING_M[1])
    chain = [pre_qa, post_qa]
    if with_twin:
        twin, chain, stack, stack_dates = _twin(plot, twin_grid, twin_mask, twin_ring, pre, post, pre_qa, post_qa, fresh)
        neighbours.counterfactual = twin
        _pretrend(neighbours, stack, stack_dates, pre.date, twin_mask, twin_ring, seed)
    if with_far:
        neighbours.far_placebo = _far_test(plot, mask, pre, post, pre_a, plot_delta, seed, fresh)

    optical = OpticalEvidence(
        scenes_considered=chain,
        pre=pre_stats,
        post=post_stats,
        plot_delta_ndvi=r4(plot_delta),
        drop_frac=r4(drop_frac),
        iqr_delta=r4(iqr_delta),
        within_plot_pattern=ix.within_plot_pattern(drop_frac, iqr_delta),
        post_bare_fraction=r4(bare),
    )
    return optical, neighbours


def optical_compare(polygon: dict, pre_id: str, post_id: str, seed: int) -> tuple[OpticalEvidence, NeighbourEvidence]:
    """Plot and neighbour statistics for a pre/post pair. Raises SceneUnusable on a rejected scene."""
    return _optical_compare(polygon, pre_id, post_id, seed)


def _shift_year(d: Date, year: int) -> Date:
    try:
        return d.replace(year=year)
    except ValueError:  # 29 Feb
        return d.replace(year=year, day=28)


def _pair_delta(
    plot: Plot, pre: SceneRef, post: SceneRef, *, fresh: bool = False
) -> tuple[float | None, float | None]:
    """Plot pre NDVI and median delta on the plot grid. (None, None) if the pair has no pixels.

    History needs only NDVI, so it reads only the three bands NDVI needs.
    """
    grid = plot.grid()
    mask = plot.stats_mask(grid)
    bands = read_many([(s.id, b) for s in (pre, post) for b in ("B04", "B08", "SCL")], grid, fresh=fresh)

    def layer(scene: SceneRef, allow_water: bool) -> np.ndarray:
        got = bands[scene.id]
        if got["B04"] is None or got["B08"] is None or got["SCL"] is None:
            raise SceneUnusable(f"{scene.id}: bands needed for history are missing")
        offset = _offset(scene)
        vi = ix.ndvi(ix.to_reflectance(got["B08"], offset), ix.to_reflectance(got["B04"], offset))
        vi[~ix.clear_mask(got["SCL"], allow_water=allow_water)] = np.nan
        return vi

    a, b = layer(pre, False), layer(post, True)
    pair = mask & np.isfinite(a) & np.isfinite(b)
    if not pair.any():
        return None, None
    return float(np.median(a[mask & np.isfinite(a)])), float(np.median((b - a)[pair]))


def _first_accepted(scenes: list[SceneRef], plot: Plot) -> SceneRef | None:
    for scene in scenes:
        if to_scene_qa(scene, raw_qa(scene, plot, lite=True)).status == "accepted":
            return scene
    return None


def _year_row(plot: Plot, year: int, pre: SceneRef | None, post: SceneRef | None, note: str | None, fresh=False) -> HistoryYear:
    if pre is None or post is None:
        return HistoryYear(
            year=year,
            pre_scene_id=pre.id if pre else None,
            post_scene_id=post.id if post else None,
            pre_ndvi=None,
            delta_ndvi=None,
            note=note or "no accepted scene pair in this calendar window",
        )
    pre_ndvi, delta = _pair_delta(plot, pre, post, fresh=fresh)
    return HistoryYear(
        year=year,
        pre_scene_id=pre.id,
        post_scene_id=post.id,
        pre_ndvi=r4(pre_ndvi),
        delta_ndvi=r4(delta),
        note=note or (f"{pre.date} to {post.date}" if delta is not None else "no pixel valid in both scenes"),
    )


def _summarise_history(
    rows: list[HistoryYear], current_delta: float | None, current_pre_ndvi: float | None
) -> HistoryEvidence:
    deltas = [r.delta_ndvi for r in rows if r.delta_ndvi is not None]
    typical = float(np.mean(deltas)) if deltas else None
    excess = current_delta - typical if typical is not None and current_delta is not None else None
    down = False
    notes = []
    if current_pre_ndvi is not None:
        far = [r for r in rows if r.pre_ndvi is not None and abs(r.pre_ndvi - current_pre_ndvi) > HISTORY_DOWNWEIGHT]
        if far:
            down = True
            notes.append(
                "pre-event NDVI differs by more than 0.2 in " + ", ".join(str(r.year) for r in far)
                + "; crop or sowing date may differ, so this comparison is weak"
            )
    if not deltas:
        notes.append("no usable history for this calendar window")
    return HistoryEvidence(
        years=rows, typical_delta=r4(typical), excess_vs_history=r4(excess), downweighted=down,
        note=" ".join(notes) or None,
    )


def history(
    polygon: dict,
    event_date: Date,
    years: tuple[int, ...] | list[int] | None = None,
    *,
    current_delta: float | None = None,
    current_pre_ndvi: float | None = None,
) -> HistoryEvidence:
    """The same plot, same calendar window, in earlier years.

    Pass `current_delta` and `current_pre_ndvi` from the optical comparison to get
    `excess_vs_history` and the crop-rotation down-weighting. Without them both stay unmeasured.
    """
    plot = parse_plot(polygon)
    if years is None:
        years = (event_date.year - 1, event_date.year - 2)
    rows = []
    for year in years:
        e = _shift_year(event_date, year)
        pre_scenes = search_scenes(S2_COLLECTION, plot, e - timedelta(days=PRE_WINDOW_DAYS), e)
        post_scenes = search_scenes(S2_COLLECTION, plot, e + timedelta(days=1), e + timedelta(days=POST_WINDOW_DAYS))
        pre = _first_accepted(sorted(pre_scenes, key=lambda s: s.datetime, reverse=True), plot)
        post = _first_accepted(sorted(post_scenes, key=lambda s: s.datetime), plot)
        rows.append(_year_row(plot, year, pre, post, None))
    return _summarise_history(rows, current_delta, current_pre_ndvi)


def history_from_ids(
    polygon: dict,
    scene_ids: list[str],
    *,
    current_delta: float | None = None,
    current_pre_ndvi: float | None = None,
    fresh: bool = False,
) -> HistoryEvidence:
    """Recompute history from the pinned scene ids, so replay does not depend on a new search."""
    plot = parse_plot(polygon)
    by_year: dict[int, list[SceneRef]] = {}
    for sid in scene_ids:
        s = get_scene(sid, plot)
        by_year.setdefault(s.date.year, []).append(s)
    rows = []
    for year in sorted(by_year, reverse=True):
        pair = sorted(by_year[year], key=lambda s: s.datetime)
        if len(pair) != 2:
            rows.append(_year_row(plot, year, None, None, "pinned ids do not form a pre/post pair"))
            continue
        rows.append(_year_row(plot, year, pair[0], pair[1], None, fresh=fresh))
    return _summarise_history(rows, current_delta, current_pre_ndvi)


def history_scene_ids(evidence: HistoryEvidence) -> list[str]:
    """The flat id list for ReplayCore.history_scene_ids. Only years that have a complete pair."""
    out: list[str] = []
    for row in evidence.years:
        if row.pre_scene_id and row.post_scene_id:
            out += [row.pre_scene_id, row.post_scene_id]
    return out


def timeline(polygon: dict, start: Date, end: Date) -> list[TimelinePoint]:
    """Every pass in the window with plot NDVI, or VV and VH, and its QA status. Oldest first."""
    plot = parse_plot(polygon)
    grid = plot.grid()
    mask = plot.stats_mask(grid)
    points: list[TimelinePoint] = []

    s2 = sorted(search_scenes(S2_COLLECTION, plot, start, end), key=lambda s: (s.datetime, s.id))
    for scene, qa in zip(s2, qa_chain(s2, plot, lite=True)):
        value = None
        if qa.status != "rejected":
            bands = read_assets(scene.id, ["B04", "B08", "SCL"], grid)
            offset = _offset(scene)
            vi = ix.ndvi(ix.to_reflectance(bands["B08"], offset), ix.to_reflectance(bands["B04"], offset))
            good = mask & ix.clear_mask(bands["SCL"], allow_water=True) & np.isfinite(vi)
            if good.any():
                value = r4(np.median(vi[good]))
        points.append(TimelinePoint(date=scene.date, sensor="s2", ndvi=value, qa=qa.status))

    # The timeline only plots NDVI, so its scenes need only the bands NDVI uses.
    s1 = sorted(_search_s1_tolerant(plot, start, end), key=lambda s: (s.datetime, s.id))
    for scene, qa in zip(s1, qa_chain(s1, plot)):
        vv_db = vh_db = None
        if qa.status != "rejected":
            bands = read_assets(scene.id, ["vv", "vh"], grid, is_float=True)
            vv_db = _plot_db(bands["vv"], mask)
            vh_db = _plot_db(bands["vh"], mask)
        points.append(TimelinePoint(date=scene.date, sensor="s1", vh_db=vh_db, vv_db=vv_db, qa=qa.status))
    points.sort(key=lambda p: (p.date, p.sensor))
    return points


def _search_s1_tolerant(plot: Plot, start: Date, end: Date) -> list[SceneRef]:
    """Radar is sparser than optical, so 'nothing in 90 days' should not fail the whole timeline."""
    try:
        return search_scenes(S1_COLLECTION, plot, start, end)
    except PlotError:
        return []


def _plot_db(arr: np.ndarray | None, mask: np.ndarray) -> float | None:
    if arr is None:
        return None
    vals = arr[mask]
    vals = vals[np.isfinite(vals) & (vals > 0)]
    return r4(np.median(10 * np.log10(vals))) if vals.size else None

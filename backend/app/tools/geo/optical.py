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
from .placebo import MIN_PLACEBOS, build_placebo_fields, sample_placements
from .qa import apply_q5, qa_chain, qa_one, raw_qa, to_scene_qa
from .raster import read_assets, read_many
from .stac import get_scene, search_scenes
from .twin import field_twin

PRE_NDVI_TOLERANCE = 0.15
RING_OUTERS_M = (RING_M[1], 3000, 5000)  # widen only when a smaller ring has too few placements
TWIN_PRE_DAYS = 30
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
        return ix.boa_offset(scene.processing_baseline)
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

    placements = sample_placements(
        mask, ring, both, pre.ndvi, delta, plot_pre_median, seed, PRE_NDVI_TOLERANCE
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


def _twin(plot: Plot, grid: Grid, mask: np.ndarray, ring: np.ndarray, pre: SceneRef, post: SceneRef, fresh: bool):
    """Build the field twin and return it with the QA of every scene in its window."""
    candidates = search_scenes(S2_COLLECTION, plot, pre.date - timedelta(days=TWIN_PRE_DAYS), post.date)
    by_id = {s.id: s for s in candidates}
    by_id[pre.id] = pre
    by_id[post.id] = post
    # A pass the agent did not pick may share a date with the chosen scene; keep the chosen one.
    chosen_dates = {pre.date: pre.id, post.date: post.id}
    scenes = [s for s in by_id.values() if chosen_dates.get(s.date, s.id) == s.id]
    qas = qa_chain(scenes, plot, fresh=fresh)
    status = {q.id: q.status for q in qas}
    used = sorted(
        (s for s in scenes if status[s.id] == "accepted" or s.id in (pre.id, post.id)),
        key=lambda s: (s.datetime, s.id),
    )
    used = [s for s in used if s.date <= post.date]
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
    stack = np.stack(layers)
    dates = [s.date for s in used]
    n_pre = sum(1 for s in used if s.date <= pre.date)
    twin = field_twin(stack, dates, n_pre, dates.index(post.date), mask, ring)
    return twin, qas


def _optical_compare(
    polygon: dict, pre_id: str, post_id: str, seed: int, *, fresh: bool = False
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
    twin, chain = _twin(plot, twin_grid, twin_mask, twin_ring, pre, post, fresh)
    neighbours.counterfactual = twin

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
    """Plot pre NDVI and median delta on the plot grid. (None, None) if the pair has no pixels."""
    grid = plot.grid()
    mask = plot.stats_mask(grid)
    a = _load_scene(pre, grid, post=False, red_edge=False, fresh=fresh)
    b = _load_scene(post, grid, post=True, red_edge=False, fresh=fresh)
    pair = mask & a.valid & b.valid
    if not pair.any():
        return None, None
    return float(np.median(a.ndvi[mask & a.valid])), float(np.median((b.ndvi - a.ndvi)[pair]))


def _first_accepted(scenes: list[SceneRef], plot: Plot) -> SceneRef | None:
    for scene in scenes:
        if qa_one(scene, plot).status == "accepted":
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
    for scene, qa in zip(s2, qa_chain(s2, plot)):
        value = None
        if qa.status != "rejected":
            bands = read_assets(scene.id, ["B04", "B08", "SCL"], grid)
            offset = _offset(scene)
            vi = ix.ndvi(ix.to_reflectance(bands["B08"], offset), ix.to_reflectance(bands["B04"], offset))
            good = mask & ix.clear_mask(bands["SCL"], allow_water=True) & np.isfinite(vi)
            if good.any():
                value = r4(np.median(vi[good]))
        points.append(TimelinePoint(date=scene.date, sensor="s2", ndvi=value, qa=qa.status))

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

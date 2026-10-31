"""Village witness and The Ten-Field Draw (para 21.5.8 simulated on real pixels).

This draws from cropland, not the real intimation list, and uses a satellite change index, not
assessed crop loss. The insured area is unknown, so `affected_share` is an indicator and not the
legal 25% test. Those caveats belong beside the numbers wherever they are shown.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pyproj import Transformer

from app.evidence.schema import SurveyDraw, SurveyLottery, VillageWitness

from . import indices as ix
from .base import RING_M, S1_COLLECTION, S2_COLLECTION, SceneUnusable, r4
from .grid import Grid, Plot, parse_plot
from .optical import PRE_NDVI_TOLERANCE, PRE_SPREAD_TOLERANCE, _load_scene, _require_usable
from .placebo import HIST_BINS, sample_placements
from .qa import apply_q5, qa_one, raw_qa, to_scene_qa
from .sar import PRE_VH_TOLERANCE_DB, SMOOTH_PX, _load, nan_median_filter, water_threshold
from .stac import get_scene

VILLAGE_RADIUS_M = 3000
N_SIMULATIONS = 1000
PARCELS_PER_SURVEY = 10
N_SAMPLE_DRAWS = 8
MAX_CANDIDATES = 1000
MIN_CANDIDATES = 30
CLUSTER_CELL_M = 1000
MIN_OCCUPIED_CELLS = 5
MAX_SHARE_IN_ONE_CELL = 0.5
CROP_MIN_PRE_NDVI = 0.30
OPTICAL_DROP = -0.15
SAR_DROP_DB = -3.0
# Below these, "half of this plot's change" would be half of noise, so that share is not reported.
MIN_MEANINGFUL_DROP = {"s2": -0.05, "s1": -1.0}


@dataclass(frozen=True)
class ChangeMap:
    """One sensor's change map on a grid, with what the placement sampler needs."""

    sensor: str
    statistic: str
    grid: Grid
    change: np.ndarray  # NaN where not valid in both scenes
    pre: np.ndarray  # the variable that defines comparability
    valid: np.ndarray
    mask: np.ndarray
    plot_value: float
    plot_pre: float
    tolerance: float
    plot_pre_iqr: float | None
    spread_tolerance: float | None
    affected: np.ndarray  # per-pixel "change consistent with damage"
    comparable: np.ndarray  # per-pixel cropland comparable to this plot, before any ring
    definition: str


def normalise_sensor(sensor: str) -> str:
    value = str(sensor).lower()
    if value in ("s2", "optical", S2_COLLECTION):
        return "s2"
    if value in ("s1", "sar", S1_COLLECTION):
        return "s1"
    raise ValueError(f"sensor must be 's2' or 's1', got {sensor!r}")


def optical_change(plot: Plot, grid: Grid, pre_id: str, post_id: str, fresh: bool) -> ChangeMap:
    pre = get_scene(pre_id, plot)
    post = get_scene(post_id, plot)
    if pre.collection != S2_COLLECTION or post.collection != S2_COLLECTION:
        raise SceneUnusable("sensor 's2' needs two Sentinel-2 scenes")
    if pre.datetime >= post.datetime:
        raise SceneUnusable(f"the pre scene ({pre.date}) must be earlier than the post scene ({post.date})")
    pre_qa = qa_one(pre, plot, fresh=fresh)
    post_qa = to_scene_qa(post, apply_q5(raw_qa(post, plot, fresh=fresh), post.date, pre_qa))
    _require_usable(pre_qa)
    _require_usable(post_qa)
    a = _load_scene(pre, grid, post=False, red_edge=False, fresh=fresh)
    b = _load_scene(post, grid, post=True, red_edge=False, fresh=fresh)
    mask = plot.stats_mask(grid)
    both = a.valid & b.valid
    change = np.where(both, b.ndvi - a.ndvi, np.nan)
    if not (mask & both).any():
        raise SceneUnusable("the plot has no pixel that is valid in both scenes")
    plot_pre = float(np.median(a.ndvi[mask & a.valid]))
    plot_value = float(np.median(change[mask & both]))
    comparable = both & (a.ndvi >= CROP_MIN_PRE_NDVI) & (np.abs(a.ndvi - plot_pre) <= PRE_NDVI_TOLERANCE)
    harvest_like = (b.ndvi < ix.BARE_NDVI) & (b.bsi > 0)
    affected = comparable & (change <= OPTICAL_DROP) & ~harvest_like
    definition = (
        f"share of comparable cropland pixels ({RING_M[0]} m to the stated radius; pre NDVI at least "
        f"{CROP_MIN_PRE_NDVI:.2f} and within {PRE_NDVI_TOLERANCE:.2f} of this plot's) whose NDVI fell by at least "
        f"{abs(OPTICAL_DROP):.2f}, excluding harvest-like bare soil after the event (NDVI below {ix.BARE_NDVI:.2f} "
        "and BSI above 0). An indicator from a satellite index, not the legal 25%-of-insured-area test"
    )
    q25, q75 = np.percentile(a.ndvi[mask & both], [25, 75])
    return ChangeMap(
        "s2", "delta_ndvi", grid, change, a.ndvi, both, mask, plot_value, plot_pre,
        PRE_NDVI_TOLERANCE, float(q75 - q25), PRE_SPREAD_TOLERANCE, affected, comparable, definition,
    )


def sar_change(plot: Plot, grid: Grid, pre_id: str, post_id: str, fresh: bool) -> ChangeMap:
    pre = get_scene(pre_id, plot)
    post = get_scene(post_id, plot)
    if pre.collection != S1_COLLECTION or post.collection != S1_COLLECTION:
        raise SceneUnusable("sensor 's1' needs two Sentinel-1 RTC scenes")
    if pre.datetime >= post.datetime:
        raise SceneUnusable(f"the pre scene ({pre.date}) must be earlier than the post scene ({post.date})")
    if pre.relative_orbit != post.relative_orbit or pre.orbit_state != post.orbit_state:
        raise SceneUnusable(
            f"orbits differ ({pre.orbit_state} {pre.relative_orbit} vs {post.orbit_state} {post.relative_orbit}); "
            "radar is only comparable within one relative orbit and pass direction"
        )
    vv_a, vh_a = _load(pre.id, grid, fresh)
    vv_b, vh_b = _load(post.id, grid, fresh)
    both = np.isfinite(vv_a) & np.isfinite(vv_b) & np.isfinite(vh_a) & np.isfinite(vh_b)
    mask = plot.stats_mask(grid)
    if not (mask & both).any():
        raise SceneUnusable("the plot has no pixel with radar data in both scenes")
    change = np.where(both, vh_b - vh_a, np.nan)
    plot_pre = float(np.median(vh_a[mask & both]))
    plot_value = float(np.median(change[mask & both]))
    smooth_pre = nan_median_filter(vh_a, SMOOTH_PX)
    smooth_change = nan_median_filter(change, SMOOTH_PX)
    threshold, how = water_threshold(vv_a[both], vv_b[both])
    water_pre = nan_median_filter(vv_a, 3) < threshold
    water_post = nan_median_filter(vv_b, 3) < threshold
    comparable = both & ~water_pre & (np.abs(smooth_pre - plot_pre) <= PRE_VH_TOLERANCE_DB)
    affected = comparable & ((smooth_change <= SAR_DROP_DB) | water_post)
    definition = (
        f"share of comparable land pixels ({RING_M[0]} m to the stated radius; pre VH within "
        f"{PRE_VH_TOLERANCE_DB:.0f} dB of this plot's and not water before) that became water ({how}) or whose "
        f"smoothed VH fell by at least {abs(SAR_DROP_DB):.0f} dB. Radar cannot separate harvest from damage, so "
        "harvest is NOT excluded here. An indicator, not the legal 25%-of-insured-area test"
    )
    return ChangeMap(
        "s1", "vh_change_db", grid, change, vh_a, both, mask, plot_value, plot_pre,
        PRE_VH_TOLERANCE_DB, None, None, affected, comparable, definition,
    )


def simulate_surveys(
    values: np.ndarray, seed: int, n_simulations: int = N_SIMULATIONS, k: int = PARCELS_PER_SURVEY
) -> tuple[np.ndarray, np.ndarray]:
    """Draw k parcels without replacement, n_simulations times. Returns averages and index draws."""
    rng = np.random.default_rng(seed)
    draws = np.stack([rng.choice(values.size, size=k, replace=False) for _ in range(n_simulations)])
    return values[draws].mean(axis=1), draws


def share_below_half(averages: np.ndarray, plot_value: float, sensor: str) -> float | None:
    """Share of surveys whose average drop is under half of this plot's drop.

    None when this plot has no meaningful drop: half of a noise-level change is not a finding.
    """
    if plot_value > MIN_MEANINGFUL_DROP[sensor]:
        return None
    return float(np.mean(averages > plot_value / 2))


def clustering_problem(offsets: np.ndarray, res_m: int) -> str | None:
    """Reason why candidates are too bunched for a 'random parcels across the area' reading."""
    cell = max(1, CLUSTER_CELL_M // res_m)
    cells, counts = np.unique(offsets // cell, axis=0, return_counts=True)
    top = counts.max() / counts.sum()
    if cells.shape[0] < MIN_OCCUPIED_CELLS:
        return f"candidate parcels fall in only {cells.shape[0]} 1 km cells; too clustered to represent the area"
    if top > MAX_SHARE_IN_ONE_CELL:
        return f"{top:.0%} of candidate parcels fall in a single 1 km cell; too clustered to represent the area"
    return None


def _lottery(change: ChangeMap, plot: Plot, ring: np.ndarray, seed: int) -> SurveyLottery:
    if change.sensor == "s2" and change.plot_pre < CROP_MIN_PRE_NDVI:
        return SurveyLottery(
            n_simulations=0, statistic=change.statistic, plot_value=r4(change.plot_value), n_candidate_parcels=0,
            average_median=None, average_p05=None, average_p95=None, share_below_half_of_plot=None, seed=seed,
            insufficient_reason=(
                f"this plot's pre-event NDVI is {change.plot_pre:.2f}, under {CROP_MIN_PRE_NDVI:.2f}: no green crop "
                "before the event, so there is no comparable cropland to draw from"
            ),
        )
    # Comparability is judged on each parcel's median, the same rule as the placebo test.
    placements = sample_placements(
        change.mask, ring, change.valid, change.pre,
        np.nan_to_num(change.change), change.plot_pre, seed, change.tolerance,
        target=MAX_CANDIDATES, allow_overlap=False,
        plot_pre_iqr=change.plot_pre_iqr, spread_tolerance=change.spread_tolerance,
    )
    n = int(placements.values.size)
    reason = None
    if n < MIN_CANDIDATES:
        reason = f"only {n} non-overlapping comparable parcels in the window; need {MIN_CANDIDATES}"
    elif (problem := clustering_problem(placements.offsets, change.grid.res)) is not None:
        reason = problem
    if reason:
        return SurveyLottery(
            n_simulations=0, statistic=change.statistic, plot_value=r4(change.plot_value), n_candidate_parcels=n,
            average_median=None, average_p05=None, average_p95=None, share_below_half_of_plot=None,
            seed=seed, insufficient_reason=reason,
        )

    averages, draws = simulate_surveys(placements.values, seed)
    p05, p50, p95 = np.percentile(averages, [5, 50, 95])
    counts, edges = np.histogram(averages, bins=HIST_BINS)
    rows, cols = np.nonzero(change.mask)
    grid = change.grid
    to_ll = Transformer.from_crs(grid.epsg, 4326, always_xy=True)
    rel_r, rel_c = rows.mean() - rows.min() + 0.5, cols.mean() - cols.min() + 0.5
    xs = grid.left + (placements.offsets[:, 1] + rel_c) * grid.res
    ys = grid.top - (placements.offsets[:, 0] + rel_r) * grid.res
    lons, lats = to_ll.transform(xs, ys)
    sample = [
        SurveyDraw(
            parcels=[(round(float(lons[i]), 6), round(float(lats[i]), 6)) for i in draws[d]],
            average=r4(averages[d]),
        )
        for d in range(min(N_SAMPLE_DRAWS, draws.shape[0]))
    ]
    return SurveyLottery(
        n_simulations=int(averages.size),
        statistic=change.statistic,
        plot_value=r4(change.plot_value),
        n_candidate_parcels=n,
        average_median=r4(p50),
        average_p05=r4(p05),
        average_p95=r4(p95),
        share_below_half_of_plot=r4(share_below_half(averages, change.plot_value, change.sensor)),
        histogram_edges=[r4(e) for e in edges],
        histogram_counts=[int(c) for c in counts],
        sample_draws=sample,
        seed=seed,
    )


def _village_witness(polygon: dict, pre_id: str, post_id: str, seed: int, sensor: str, *, fresh: bool = False) -> VillageWitness:
    plot = parse_plot(polygon)
    which = normalise_sensor(sensor)
    grid = plot.grid(VILLAGE_RADIUS_M)
    build = optical_change if which == "s2" else sar_change
    change = build(plot, grid, pre_id, post_id, fresh)
    dist = plot.distance_m(grid)
    ring = (dist >= RING_M[0]) & (dist <= VILLAGE_RADIUS_M)
    cropland = ring & change.comparable
    n_cropland = int(cropland.sum())
    affected = float(np.mean(change.affected[cropland])) if n_cropland else None
    definition = change.definition
    if n_cropland == 0:
        definition = "not computed: no comparable cropland pixels were valid in both scenes. " + definition
    return VillageWitness(
        radius_m=VILLAGE_RADIUS_M,
        sensor=which,
        n_cropland_pixels=n_cropland,
        affected_share=r4(affected),
        affected_definition=definition,
        lottery=_lottery(change, plot, ring, seed),
    )


def village_witness(polygon: dict, pre_id: str, post_id: str, seed: int, sensor: str) -> VillageWitness:
    """Affected share and The Ten-Field Draw around the plot. `sensor` is 's2' or 's1'."""
    return _village_witness(polygon, pre_id, post_id, seed, sensor)

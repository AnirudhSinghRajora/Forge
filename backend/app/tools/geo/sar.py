"""Sentinel-1 RTC comparison: same orbit only, in dB, with inundation and a placebo on VH change."""
from __future__ import annotations

from datetime import date as Date

import numpy as np
from scipy import ndimage

from app.evidence.schema import PlaceboTest, SarEvidence

from . import indices as ix
from .base import RING_M, S1_COLLECTION, SceneRef, SceneUnusable, r4
from .grid import Grid, Plot, parse_plot
from .placebo import MIN_PLACEBOS, build_placebo_fields, sample_placements
from .qa import raw_qa
from .raster import read_assets
from .stac import get_scene, search_scenes

WATER_DEFAULT_DB = -18.0
OTSU_RANGE_DB = (-26.0, -13.0)
OTSU_MIN_CLASS_SHARE = 0.02
OTSU_MIN_SEPARATION_DB = 5.0
PRE_VH_TOLERANCE_DB = 2.0
SMOOTH_PX = 5
RING_OUTERS_M = (RING_M[1], 3000)
MIN_PLOT_VALID = 0.8


def search_sar(polygon: dict, start: Date, end: Date) -> list[SceneRef]:
    """Sentinel-1 RTC passes over the plot in [start, end], one per pass, oldest first."""
    return search_scenes(S1_COLLECTION, parse_plot(polygon), start, end)


def to_db(linear: np.ndarray) -> np.ndarray:
    """10 log10 of linear backscatter; NaN where the value is missing or non-positive."""
    out = np.full(linear.shape, np.nan, dtype=np.float32)
    good = np.isfinite(linear) & (linear > 0)
    out[good] = 10.0 * np.log10(linear[good])
    return out


def nan_median_filter(arr: np.ndarray, size: int) -> np.ndarray:
    """Median filter that ignores NaNs in the window by using +inf/-inf balancing is overkill here;
    missing pixels are rare in RTC, so they are filled with the image median and masked afterwards."""
    good = np.isfinite(arr)
    if not good.any():
        return arr.copy()
    filled = np.where(good, arr, float(np.median(arr[good])))
    out = ndimage.median_filter(filled, size=size, mode="nearest")
    out[~good] = np.nan
    return out.astype(np.float32)


def water_threshold(vv_pre_db: np.ndarray, vv_post_db: np.ndarray) -> tuple[float, str]:
    """Otsu on pooled context VV when there is a real dark class, otherwise -18 dB. Says which."""
    pooled = np.concatenate([vv_pre_db[np.isfinite(vv_pre_db)], vv_post_db[np.isfinite(vv_post_db)]])
    fixed = f"fixed {WATER_DEFAULT_DB:.0f} dB threshold"
    if pooled.size == 0:
        return WATER_DEFAULT_DB, fixed + " (no context data)"
    t = ix.otsu_threshold(pooled)
    if not np.isfinite(t) or not OTSU_RANGE_DB[0] <= t <= OTSU_RANGE_DB[1]:
        shown = "undefined" if not np.isfinite(t) else f"{t:.1f} dB"
        return WATER_DEFAULT_DB, f"{fixed} (Otsu gave {shown}, outside the plausible water range)"
    below, above = pooled[pooled < t], pooled[pooled >= t]
    share = below.size / pooled.size
    if share < OTSU_MIN_CLASS_SHARE:
        return WATER_DEFAULT_DB, f"{fixed} (Otsu dark class only {share:.1%} of context)"
    sep = float(np.median(above) - np.median(below))
    if sep < OTSU_MIN_SEPARATION_DB:
        return WATER_DEFAULT_DB, f"{fixed} (Otsu classes only {sep:.1f} dB apart, not bimodal)"
    return t, f"Otsu threshold {t:.1f} dB on context VV"


def _unusable(pre: SceneRef, post: SceneRef, reason: str) -> SarEvidence:
    return SarEvidence(
        pre_scene_id=pre.id,
        post_scene_id=post.id,
        pre_date=pre.date,
        post_date=post.date,
        orbit_direction=post.orbit_state,
        relative_orbit=post.relative_orbit,
        usable=False,
        reason=reason,
    )


def _load(scene_id: str, grid: Grid, fresh: bool) -> tuple[np.ndarray, np.ndarray]:
    bands = read_assets(scene_id, ["vv", "vh"], grid, is_float=True, fresh=fresh)
    if bands["vv"] is None or bands["vh"] is None:
        raise SceneUnusable(f"{scene_id}: VV or VH asset is missing")
    return to_db(bands["vv"]), to_db(bands["vh"])


def _sar_compare(polygon: dict, pre_id: str, post_id: str, seed: int, *, fresh: bool = False) -> SarEvidence:
    plot: Plot = parse_plot(polygon)
    pre = get_scene(pre_id, plot)
    post = get_scene(post_id, plot)
    if pre.collection != S1_COLLECTION or post.collection != S1_COLLECTION:
        raise SceneUnusable("sar_compare needs two Sentinel-1 RTC scenes")
    if pre.datetime >= post.datetime:
        raise SceneUnusable(f"the pre scene ({pre.date}) must be earlier than the post scene ({post.date})")
    if pre.relative_orbit != post.relative_orbit or pre.orbit_state != post.orbit_state:
        return _unusable(
            pre, post,
            f"orbits differ ({pre.orbit_state} {pre.relative_orbit} vs {post.orbit_state} {post.relative_orbit}); "
            "radar is only comparable within one relative orbit and pass direction",
        )
    for scene in (pre, post):
        raw = raw_qa(scene, plot, fresh=fresh)
        if raw.status == "rejected":
            return _unusable(pre, post, f"{scene.id} failed QA: {'; '.join(raw.reasons)}")

    placebo: PlaceboTest | None = None
    for outer in RING_OUTERS_M:
        grid = plot.grid(max(outer, 1500))
        mask = plot.stats_mask(grid)
        vv_a, vh_a = _load(pre.id, grid, fresh)
        vv_b, vh_b = _load(post.id, grid, fresh)
        both = np.isfinite(vv_a) & np.isfinite(vv_b) & np.isfinite(vh_a) & np.isfinite(vh_b)
        pick = mask & both
        valid_share = float(pick.sum() / mask.sum())
        if valid_share < MIN_PLOT_VALID:
            return _unusable(pre, post, f"only {valid_share:.0%} of plot pixels have radar data in both scenes")

        delta = vh_b - vh_a
        plot_change = float(np.median(delta[pick]))
        plot_pre_vh = float(np.median(vh_a[pick]))

        dist = plot.distance_m(grid)
        ring = (dist >= RING_M[0]) & (dist <= outer)
        # Comparability uses smoothed pre VH: raw speckle would otherwise select on noise.
        vh_smooth = nan_median_filter(vh_a, SMOOTH_PX)
        comparable = ring & both & (np.abs(vh_smooth - plot_pre_vh) <= PRE_VH_TOLERANCE_DB)
        n_comparable = int(comparable.sum())
        neighbour = float(np.median(delta[comparable])) if n_comparable else None

        placements = sample_placements(mask, ring, both, vh_a, delta, plot_pre_vh, seed, PRE_VH_TOLERANCE_DB)
        placebo = PlaceboTest(**build_placebo_fields(placements, plot_change, "median_vh_change_db", seed))
        if placebo.n_placebos >= MIN_PLACEBOS:
            break

    context_grid_mask = np.isfinite(vv_a) & np.isfinite(vv_b)
    threshold, how = water_threshold(vv_a[context_grid_mask], vv_b[context_grid_mask])
    water_a = nan_median_filter(vv_a, 3) < threshold
    water_b = nan_median_filter(vv_b, 3) < threshold
    water_pre = float(np.mean(water_a[pick]))
    water_post = float(np.mean(water_b[pick]))
    new_water = float(np.mean((water_b & ~water_a)[pick]))
    ring_both = ring & both
    ring_new = float(np.mean((water_b & ~water_a)[ring_both])) if ring_both.any() else None

    reason = f"{how}; {pre.orbit_state} orbit {pre.relative_orbit}, {(post.date - pre.date).days} days apart"
    if ring_new is not None:
        reason += f"; new water in the surrounding ring {ring_new:.1%}"
    return SarEvidence(
        pre_scene_id=pre.id,
        post_scene_id=post.id,
        pre_date=pre.date,
        post_date=post.date,
        orbit_direction=pre.orbit_state,
        relative_orbit=pre.relative_orbit,
        vv_pre_db=r4(np.median(vv_a[pick])),
        vv_post_db=r4(np.median(vv_b[pick])),
        vh_pre_db=r4(plot_pre_vh),
        vh_post_db=r4(np.median(vh_b[pick])),
        vh_change_db=r4(plot_change),
        neighbour_vh_change_db=r4(neighbour),
        vh_excess_db=r4(plot_change - neighbour) if neighbour is not None else None,
        water_frac_pre=r4(water_pre),
        water_frac_post=r4(water_post),
        new_water_frac=r4(new_water),
        placebo=placebo,
        usable=True,
        reason=reason,
    )


def sar_compare(polygon: dict, pre_id: str, post_id: str, seed: int) -> SarEvidence:
    """VH change and inundation for a same-orbit pair. Mismatched orbits give usable=False."""
    return _sar_compare(polygon, pre_id, post_id, seed)


__all__ = ["MIN_PLACEBOS", "sar_compare", "search_sar", "to_db", "water_threshold"]

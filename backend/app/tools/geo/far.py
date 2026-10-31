"""The far test: did this field change more than comparable fields outside the storm area?

Same-shape placebos in a 5-12 km annulus (Addendum 4). The ring test asks how local a loss is; a swath
wider than the ring defeats it because the ring shares the damage. For an event bigger than 12 km this
test loses power as well, and history and the pre-event trend have to carry the case.

A full 24 km window costs about 45 MB, so this reads a seeded sample of windows aligned to the COG's
own blocks, one per sector so they cannot all land on one side of a storm. Selection uses geometry and
the seed only, never the pixels. Placebos come only from the sampled windows.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .base import PlotError, SceneRef
from .grid import Grid, Plot
from .placebo import MIN_PLACEBOS, TARGET_PLACEBOS, PlacementResult, sample_placements
from .raster import block_layout, read_many

FAR_INNER_M = 5000
FAR_OUTER_M = 12000
N_SECTORS = 6


def sector_windows(
    cx: float, cy: float, left: float, top: float, block_m: int, seed: int, epsg: int, res: int = 10,
) -> list[Grid]:
    """One block-aligned window per sector of the annulus around (cx, cy), chosen by seed."""
    rng = np.random.default_rng(seed)
    span = FAR_OUTER_M + block_m
    col0 = math.floor((cx - span - left) / block_m)
    col1 = math.ceil((cx + span - left) / block_m)
    row0 = math.floor((top - cy - span) / block_m)
    row1 = math.ceil((top - cy + span) / block_m)
    by_sector: list[list[tuple[int, int]]] = [[] for _ in range(N_SECTORS)]
    for row in range(row0, row1 + 1):
        for col in range(col0, col1 + 1):
            mx = left + (col + 0.5) * block_m
            my = top - (row + 0.5) * block_m
            distance = math.hypot(mx - cx, my - cy)
            if FAR_INNER_M + block_m / 2 <= distance <= FAR_OUTER_M - block_m / 4:
                angle = math.atan2(my - cy, mx - cx) % (2 * math.pi)
                by_sector[int(angle / (2 * math.pi) * N_SECTORS) % N_SECTORS].append((row, col))
    size = block_m // res
    windows = []
    for cells in by_sector:
        if cells:
            row, col = cells[int(rng.integers(len(cells)))]
            windows.append(Grid(epsg, left + col * block_m, top - row * block_m, size, size, res))
    return windows


def annulus_mask(grid: Grid, cx: float, cy: float) -> np.ndarray:
    xs = grid.left + (np.arange(grid.width) + 0.5) * grid.res
    ys = grid.top - (np.arange(grid.height) + 0.5) * grid.res
    distance = np.hypot(xs[None, :] - cx, ys[:, None] - cy)
    return (distance >= FAR_INNER_M) & (distance <= FAR_OUTER_M)


def far_placements(
    plot: Plot,
    mask: np.ndarray,
    pre: SceneRef,
    post: SceneRef,
    layer,
    plot_pre_median: float,
    plot_pre_iqr: float,
    pre_tolerance: float,
    spread_tolerance: float,
    seed: int,
    fresh: bool,
) -> PlacementResult:
    """Sample placements across the windows. `layer(scene, bands, is_post)` gives (ndvi, valid)."""
    left, top, block_px = block_layout(pre.id, "B04", fresh=fresh)
    c = plot.utm.centroid
    # The grid must be the plot's UTM. An item in another zone cannot be block-aligned here.
    windows = sector_windows(c.x, c.y, left, top, block_px * 10, seed, plot.epsg)
    if not windows:
        raise PlotError("no far windows could be placed around this plot")
    rows, cols = np.nonzero(mask)
    template = np.zeros((rows.max() - rows.min() + 1, cols.max() - cols.min() + 1), dtype=bool)
    template[rows - rows.min(), cols - cols.min()] = True

    values: list[np.ndarray] = []
    offsets: list[np.ndarray] = []
    n_non_overlapping = n_candidates = n_evaluated = 0
    per_window = math.ceil(TARGET_PLACEBOS / len(windows))
    requests = [(s.id, b) for s in (pre, post) for b in ("B04", "B08", "SCL")]
    # All windows at once: the pool bounds concurrency, and the order they arrive in changes nothing.
    with ThreadPoolExecutor(max_workers=len(windows), thread_name_prefix="geo-far") as pool:
        all_bands = list(pool.map(lambda w: read_many(requests, w, fresh=fresh), windows))
    for index, (window, bands) in enumerate(zip(windows, all_bands)):
        a, valid_a = layer(pre, bands[pre.id], False)
        b, valid_b = layer(post, bands[post.id], True)
        if a is None or b is None:
            continue
        both = valid_a & valid_b
        delta = np.nan_to_num(b - a)
        if template.shape[0] > window.height or template.shape[1] > window.width:
            continue
        local_mask = np.zeros(window.shape, dtype=bool)
        local_mask[: template.shape[0], : template.shape[1]] = template
        result = sample_placements(
            local_mask, annulus_mask(window, c.x, c.y), both, a, delta, plot_pre_median, seed + index + 1,
            pre_tolerance, target=per_window, allow_overlap=False, plot_pre_iqr=plot_pre_iqr,
            spread_tolerance=spread_tolerance,
        )
        values.append(result.values)
        offsets.append(result.offsets)
        n_non_overlapping += result.n_non_overlapping
        n_candidates += result.n_candidates
        n_evaluated += result.n_evaluated
    if not values:
        return PlacementResult(np.empty(0), np.empty((0, 2), int), 0, n_candidates, n_evaluated)
    return PlacementResult(
        np.concatenate(values), np.concatenate(offsets), n_non_overlapping, n_candidates, n_evaluated
    )


__all__ = ["FAR_INNER_M", "FAR_OUTER_M", "MIN_PLACEBOS", "annulus_mask", "far_placements", "sector_windows"]

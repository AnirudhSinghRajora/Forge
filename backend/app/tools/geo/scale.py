"""The Vanishing: one real change map block-averaged to coarser cells.

Our illustration from public satellite data, not output of YES-TECH. Blocks are anchored so the
plot centroid sits at the middle of its own block at every scale. Otherwise the plot's value would
depend on where an arbitrary grid happened to fall. All levels share one colour scale. The 10 m level
draws the map itself and reports the plot's own median change; coarser levels report their block.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from app.evidence.schema import ScaleFade, ScaleLevel

from .base import r4
from .chips import DELTA_RANGE, SAR_RANGE_DB, _colourise, _save
from .grid import Grid, Plot, parse_plot
from .village import VILLAGE_RADIUS_M, normalise_sensor, optical_change, sar_change

BLOCK_LEVELS_M = (10, 100, 500, 1000, 3000)
MIN_CELL_VALID = 0.5


def block_average(values: np.ndarray, block_px: int, centre: tuple[int, int]) -> tuple[np.ndarray, float | None, float | None]:
    """NaN-aware block mean, on the original pixel grid so every level has the same shape.

    Returns (map, value of the block containing `centre`, lowest block value). A block with under
    half of its pixels valid is NaN. Edge blocks clipped by the window are real means of fewer pixels.
    """
    if block_px <= 1:
        finite = values[np.isfinite(values)]
        value = values[centre]
        return values.copy(), (float(value) if np.isfinite(value) else None), (float(finite.min()) if finite.size else None)
    rows, cols = values.shape
    half = block_px // 2
    # Index of each row and column's block, with the centre pixel in the middle of block 0.
    row_ids = (np.arange(rows) - centre[0] + half) // block_px
    col_ids = (np.arange(cols) - centre[1] + half) // block_px
    row_ids -= row_ids.min()
    col_ids -= col_ids.min()
    n_r, n_c = int(row_ids.max()) + 1, int(col_ids.max()) + 1
    good = np.isfinite(values)
    index = row_ids[:, None] * n_c + col_ids[None, :]
    total = np.bincount(index.ravel(), weights=np.where(good, values, 0.0).ravel(), minlength=n_r * n_c)
    valid = np.bincount(index.ravel(), weights=good.astype(np.float64).ravel(), minlength=n_r * n_c)
    size = np.bincount(index.ravel(), minlength=n_r * n_c)
    with np.errstate(invalid="ignore", divide="ignore"):
        means = total / valid
    means[valid < MIN_CELL_VALID * size] = np.nan
    out = means[index].astype(np.float32)
    value = out[centre]
    finite = means[np.isfinite(means)]
    return out, (float(value) if np.isfinite(value) else None), (float(finite.min()) if finite.size else None)


def _centroid_pixel(plot: Plot, grid: Grid) -> tuple[int, int]:
    c = plot.utm.centroid
    return int((grid.top - c.y) // grid.res), int((c.x - grid.left) // grid.res)


def _scale_fade(polygon: dict, pre_id: str, post_id: str, out_dir: str | Path | None, sensor: str, *, fresh: bool = False) -> ScaleFade:
    plot = parse_plot(polygon)
    which = normalise_sensor(sensor)
    grid = plot.grid(VILLAGE_RADIUS_M)
    build = optical_change if which == "s2" else sar_change
    change = build(plot, grid, pre_id, post_id, fresh)
    centre = _centroid_pixel(plot, grid)
    cmap, limit = ("RdBu", DELTA_RANGE) if which == "s2" else ("PuOr", SAR_RANGE_DB)
    levels = []
    for block_m in BLOCK_LEVELS_M:
        layer, value, lowest = block_average(change.change, block_m // grid.res, centre)
        if block_m == BLOCK_LEVELS_M[0]:
            # "Your field": the plot's own median change. A single centre pixel is noise, not the field.
            value = change.plot_value
        path = None
        if out_dir is not None:
            target = Path(out_dir) / f"scale_{block_m}m.png"
            _save(_colourise(layer, cmap, -limit, limit), plot, grid, target)
            path = str(target)
        levels.append(ScaleLevel(block_m=block_m, plot_cell_value=r4(value), context_min=r4(lowest), chip_path=path))
    return ScaleFade(sensor=which, statistic=change.statistic, bounds=grid.lonlat_bounds(), levels=levels)


def scale_fade(polygon: dict, pre_id: str, post_id: str, out_dir: str | Path, sensor: str) -> ScaleFade:
    """Write one PNG per block size into `out_dir` and report the plot cell's value at each."""
    return _scale_fade(polygon, pre_id, post_id, out_dir, sensor)

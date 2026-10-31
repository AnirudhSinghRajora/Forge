"""Evidence chips as PNGs. Colour stretches are fixed, never per image, so pre and post compare honestly."""
from __future__ import annotations

from datetime import date as Date
from pathlib import Path

import numpy as np
from matplotlib import colormaps
from PIL import Image, ImageDraw

from app.evidence.schema import Chip

from . import indices as ix
from .base import SceneUnusable
from .grid import Grid, Plot, parse_plot
from .raster import read_assets, read_overview
from .sar import nan_median_filter, to_db
from .stac import get_scene

CLOSE_MARGIN_M = 200
TARGET_WIDTH_PX = 720
MASK_RGB = (70, 70, 70)
TRUE_COLOUR_MAX = 0.30
NDVI_RANGE = (-0.1, 0.9)
DELTA_RANGE = 0.5
SAR_RANGE_DB = 6.0
REGION_RADIUS_M = 12000
REGION_RES_M = 40  # an overview level for both 10 m bands and 20 m SCL


def _upscale_factor(grid: Grid) -> int:
    return max(1, TARGET_WIDTH_PX // grid.width)


def _colourise(values: np.ndarray, cmap: str, lo: float, hi: float) -> np.ndarray:
    """RGB uint8 with non-finite pixels in neutral grey, which no colourmap below uses at its zero."""
    norm = np.clip((values - lo) / (hi - lo), 0, 1)
    rgb = (colormaps[cmap](np.nan_to_num(norm))[..., :3] * 255).astype(np.uint8)
    rgb[~np.isfinite(values)] = MASK_RGB
    return rgb


def _save(rgb: np.ndarray, plot: Plot, grid: Grid, path: Path) -> None:
    """Nearest-neighbour upscale so a pixel stays a pixel, then draw the plot outline."""
    factor = _upscale_factor(grid)
    image = Image.fromarray(rgb, "RGB").resize((grid.width * factor, grid.height * factor), Image.NEAREST)
    draw = ImageDraw.Draw(image)
    coords = [
        ((x - grid.left) / grid.res * factor, (grid.top - y) / grid.res * factor)
        for x, y in plot.utm.exterior.coords
    ]
    draw.line(coords, fill=(255, 255, 255), width=4, joint="curve")
    draw.line(coords, fill=(0, 0, 0), width=2, joint="curve")
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def _reflectance(scene_id: str, assets: list[str], grid: Grid) -> tuple[dict, np.ndarray]:
    scene = get_scene(scene_id)
    try:
        offset = ix.scene_offset(scene.processing_baseline, scene.boa_offset_applied)
    except ValueError as exc:
        raise SceneUnusable(f"{scene_id}: {exc}") from exc
    bands = read_assets(scene_id, assets + ["SCL"], grid)
    for name in assets + ["SCL"]:
        if bands.get(name) is None:
            raise SceneUnusable(f"{scene_id}: band {name} is missing, so this chip cannot be drawn")
    return {n: ix.to_reflectance(bands[n], offset) for n in assets}, bands["SCL"]


def _true_colour(scene_id: str, grid: Grid) -> np.ndarray:
    refl, scl = _reflectance(scene_id, ["B04", "B03", "B02"], grid)
    rgb = np.stack([refl["B04"], refl["B03"], refl["B02"]], axis=-1)
    missing = ~np.all(np.isfinite(rgb), axis=-1) | (scl == 0)
    out = (np.clip(np.nan_to_num(rgb) / TRUE_COLOUR_MAX, 0, 1) ** (1 / 1.8) * 255).astype(np.uint8)
    out[missing] = MASK_RGB
    return out


def _ndvi_layer(scene_id: str, grid: Grid, *, post: bool) -> np.ndarray:
    refl, scl = _reflectance(scene_id, ["B04", "B08"], grid)
    vi = ix.ndvi(refl["B08"], refl["B04"])
    vi[~ix.clear_mask(scl, allow_water=post)] = np.nan
    return vi


def _overview_ndvi(scene_id: str, grid: Grid, *, post: bool) -> np.ndarray | None:
    """NDVI from COG overviews. For the picture only: no reported number comes from this."""
    scene = get_scene(scene_id)
    try:
        offset = ix.scene_offset(scene.processing_baseline, scene.boa_offset_applied)
    except ValueError as exc:
        raise SceneUnusable(f"{scene_id}: {exc}") from exc
    b04 = read_overview(scene_id, "B04", grid)
    b08 = read_overview(scene_id, "B08", grid)
    scl = read_overview(scene_id, "SCL", grid)
    if b04 is None or b08 is None or scl is None:
        return None
    vi = ix.ndvi(ix.to_reflectance(b08, offset), ix.to_reflectance(b04, offset))
    vi[~ix.clear_mask(scl, allow_water=post)] = np.nan
    return vi


def region_layer(plot: Plot, pre_id: str, post_id: str) -> tuple[Grid, np.ndarray] | None:
    """The wide change map around a plot, or None if a scene is not in the plot's UTM zone."""
    res = REGION_RES_M
    c = plot.utm.centroid
    size = int(2 * REGION_RADIUS_M / res)
    left = np.floor((c.x - REGION_RADIUS_M) / res) * res
    top = np.ceil((c.y + REGION_RADIUS_M) / res) * res
    grid = Grid(plot.epsg, float(left), float(top), size, size, res)
    a = _overview_ndvi(pre_id, grid, post=False)
    b = _overview_ndvi(post_id, grid, post=True)
    if a is None or b is None:
        return None
    return grid, b - a


def render_chips(
    polygon: dict,
    pre_id: str,
    post_id: str,
    out_dir: str | Path,
    sar_pre_id: str | None = None,
    sar_post_id: str | None = None,
) -> list[Chip]:
    """Write true colour, NDVI, delta and radar-change PNGs into `out_dir`.

    Close-ups cover the plot + 200 m. delta_map and sar_change cover the whole context window.
    region_map covers about 24 km at 40 m, from COG overviews; a band in it is "consistent with" a
    storm's footprint and is not proof of one.
    Grey means no valid data (cloud, shadow, or outside the image). No text is drawn on any chip.
    """
    plot = parse_plot(polygon)
    out = Path(out_dir)
    close = plot.grid(CLOSE_MARGIN_M)
    context = plot.grid()
    pre = get_scene(pre_id)
    post = get_scene(post_id)
    chips: list[Chip] = []

    def add(kind: str, rgb: np.ndarray, grid: Grid, scene_id: str | None, when: Date | None) -> None:
        path = out / f"{kind}.png"
        _save(rgb, plot, grid, path)
        chips.append(Chip(kind=kind, path=str(path), scene_id=scene_id, date=when, bounds=grid.lonlat_bounds()))

    add("true_colour_pre", _true_colour(pre_id, close), close, pre_id, pre.date)
    add("true_colour_post", _true_colour(post_id, close), close, post_id, post.date)
    add("ndvi_pre", _colourise(_ndvi_layer(pre_id, close, post=False), "RdYlGn", *NDVI_RANGE), close, pre_id, pre.date)
    add("ndvi_post", _colourise(_ndvi_layer(post_id, close, post=True), "RdYlGn", *NDVI_RANGE), close, post_id, post.date)

    delta = _ndvi_layer(post_id, context, post=True) - _ndvi_layer(pre_id, context, post=False)
    add("delta_map", _colourise(delta, "RdBu", -DELTA_RANGE, DELTA_RANGE), context, post_id, post.date)

    # The wide view: a storm's footprint, if there is one, shows up here. Same colour scale as delta_map.
    region = region_layer(plot, pre_id, post_id)
    if region is not None:
        add("region_map", _colourise(region[1], "RdBu", -DELTA_RANGE, DELTA_RANGE), region[0], post_id, post.date)

    if sar_pre_id and sar_post_id:
        a = read_assets(sar_pre_id, ["vh"], context, is_float=True)["vh"]
        b = read_assets(sar_post_id, ["vh"], context, is_float=True)["vh"]
        if a is None or b is None:
            raise SceneUnusable("VH asset is missing, so the radar chip cannot be drawn")
        change = nan_median_filter(to_db(b), 3) - nan_median_filter(to_db(a), 3)
        sar_scene = get_scene(sar_post_id)
        add("sar_change", _colourise(change, "PuOr", -SAR_RANGE_DB, SAR_RANGE_DB), context, sar_post_id, sar_scene.date)
    return chips

"""Whole-region change map and block statistics, to see whether an event has a spatial signature.

PYTHONPATH=. uv run python tests/geo_region_map.py --lat .. --lon .. --size-px 1400 --pre ID --post ID --name x
"""
from __future__ import annotations

import argparse
import math

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer

from app.tools.geo import indices as ix
from app.tools.geo.base import var_dir
from app.tools.geo.chips import DELTA_RANGE, _colourise
from app.tools.geo.grid import Grid, utm_epsg
from app.tools.geo.raster import read_assets
from app.tools.geo.scale import block_average
from app.tools.geo.stac import get_scene


def layer(scene_id: str, grid: Grid, post: bool) -> np.ndarray:
    scene = get_scene(scene_id)
    b = read_assets(scene_id, ["B04", "B08", "SCL"], grid)
    off = ix.boa_offset(scene.processing_baseline)
    vi = ix.ndvi(ix.to_reflectance(b["B08"], off), ix.to_reflectance(b["B04"], off))
    vi[~ix.clear_mask(b["SCL"], allow_water=post)] = np.nan
    return vi


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--size-px", type=int, default=1400)
    ap.add_argument("--pre", required=True)
    ap.add_argument("--post", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--mark", nargs="*", default=[], help="lat,lon points to mark")
    args = ap.parse_args()
    epsg = utm_epsg(args.lon, args.lat)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    x, y = to_utm.transform(args.lon, args.lat)
    half = args.size_px * 5
    grid = Grid(epsg, float(math.floor((x - half) / 10) * 10), float(math.ceil((y + half) / 10) * 10), args.size_px, args.size_px)
    a, b = layer(args.pre, grid, False), layer(args.post, grid, True)
    delta = b - a
    green = a >= 0.5
    d = delta[green & np.isfinite(delta)]
    print(f"valid share {np.isfinite(delta).mean():.3f}; green-before share {green.mean():.3f}")
    print("delta on pixels green before (pre NDVI >= 0.5): p1,5,25,50,75,95,99 =", np.round(np.percentile(d, [1, 5, 25, 50, 75, 95, 99]), 3).tolist())
    print(f"share of those with delta <= -0.15: {np.mean(d <= -0.15):.3f}; <= -0.30: {np.mean(d <= -0.30):.3f}")
    masked = np.where(green, delta, np.nan)
    for km in (1, 2):
        _, _, _ = block_average(masked, km * 100, (grid.height // 2, grid.width // 2))
        rows = grid.height // (km * 100)
        cols = grid.width // (km * 100)
        cells = [np.nanmedian(masked[r * km * 100: (r + 1) * km * 100, c * km * 100: (c + 1) * km * 100])
                 for r in range(rows) for c in range(cols)
                 if np.isfinite(masked[r * km * 100: (r + 1) * km * 100, c * km * 100: (c + 1) * km * 100]).mean() > 0.2]
        cells = np.array(cells)
        print(f"{km} km cells on green-before pixels: n={cells.size} median of cell medians p5,50,95 = {np.round(np.percentile(cells, [5, 50, 95]), 3).tolist()} min {cells.min():.3f} max {cells.max():.3f}")
    rgb = _colourise(delta, "RdBu", -DELTA_RANGE, DELTA_RANGE)
    image = Image.fromarray(rgb, "RGB")
    draw = ImageDraw.Draw(image)
    for point in args.mark:
        lat, lon = map(float, point.split(","))
        px, py = to_utm.transform(lon, lat)
        c, r = (px - grid.left) / 10, (grid.top - py) / 10
        draw.ellipse([c - 14, r - 14, c + 14, r + 14], outline=(0, 0, 0), width=3)
    out = var_dir() / "geo_validation" / f"region_{args.name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print("map:", out)


if __name__ == "__main__":
    main()

"""False-positive rate of the placebo test on a window with no reported event. Real data; not a pytest.

Run from backend/:  PYTHONPATH=. uv run python tests/geo_fpr_sirsa.py --n 300 --out /path/results.jsonl

Plots are random squares on ESA WorldCover cropland, a map independent of the method being tested.
The region is read once and each plot runs through the unchanged optical_compare path on crops of it.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date

import numpy as np
import pystac_client
from pyproj import Transformer

from app.tools.geo.base import STAC_URL, SceneUnusable
from app.tools.geo.grid import Grid, parse_plot
from app.tools.geo.optical import RED_EDGE_BANDS, _load_scene, _optical_compare
from app.tools.geo.qa import QA_BANDS
from app.tools.geo.raster import _read_once, prefetch_region
from app.tools.geo.stac import search_scenes

EPSG = 32643
REGION = dict(left=503000.0, top=3275000.0, width=1800, height=1800)  # about 18 x 18 km east of Sirsa town
MARGIN_PX = 320
CROPLAND = 40


def square(lon: float, lat: float, side_m: float) -> dict:
    dlat = side_m / 2 / 111_320
    dlon = dlat / math.cos(math.radians(lat))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]
    return {"type": "Polygon", "coordinates": [ring]}


def worldcover(grid: Grid) -> np.ndarray:
    w, s, e, n = grid.lonlat_bounds()
    cat = pystac_client.Client.open(STAC_URL)
    items = list(cat.search(collections=["esa-worldcover"], bbox=[w, s, e, n]).items())
    items = [i for i in items if i.properties.get("esa_worldcover:product_version", "").startswith("2") or "2021" in i.id]
    item = sorted(items, key=lambda i: i.id)[-1]
    print("land cover:", item.id, flush=True)
    return _read_once(item.assets["map"].href, grid, False)


def pick_scene(region_plot, when: date, tile: str) -> str:
    scenes = search_scenes("sentinel-2-l2a", region_plot, when, when)
    return next(s.id for s in scenes if s.tile == tile)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--pre", type=date.fromisoformat, default=date(2025, 10, 18))
    ap.add_argument("--post", type=date.fromisoformat, default=date(2025, 10, 23))
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    grid = Grid(EPSG, **REGION)
    to_ll = Transformer.from_crs(EPSG, 4326, always_xy=True)
    x0, y0 = to_ll.transform(grid.left + 9000, grid.top - 9000)
    centre_plot = parse_plot(square(x0, y0, 120))
    pre_id = pick_scene(centre_plot, args.pre, "43REN")
    post_id = pick_scene(centre_plot, args.post, "43REN")
    print("pre", pre_id, "\npost", post_id, flush=True)

    t0 = time.time()
    prefetch_region([pre_id, post_id], QA_BANDS + RED_EDGE_BANDS, grid)
    cover = worldcover(grid)
    print(f"region read in {time.time() - t0:.0f} s; cropland share {np.mean(cover == CROPLAND):.2f}", flush=True)

    pre_scene = search_scenes("sentinel-2-l2a", centre_plot, args.pre, args.pre)
    pre_ref = next(s for s in pre_scene if s.id == pre_id)
    pre_full = _load_scene(pre_ref, grid, post=False, red_edge=False)

    rng = np.random.default_rng(args.seed)
    done = skipped = attempts = 0
    t0 = time.time()
    with open(args.out, "w") as out:
        while done < args.n and attempts < args.n * 40:
            attempts += 1
            side = float(rng.uniform(100.0, 141.4))
            half = int(math.ceil(side / 20))
            r = int(rng.integers(MARGIN_PX, grid.height - MARGIN_PX))
            c = int(rng.integers(MARGIN_PX, grid.width - MARGIN_PX))
            if np.mean(cover[r - half: r + half, c - half: c + half] == CROPLAND) < 0.8:
                continue
            lon, lat = to_ll.transform(grid.left + (c + 0.5) * 10, grid.top - (r + 0.5) * 10)
            poly = square(lon, lat, side)
            plot = parse_plot(poly)
            if plot.epsg != EPSG:
                continue
            try:
                optical, neighbours = _optical_compare(poly, pre_id, post_id, seed=done, with_twin=False)
            except SceneUnusable as exc:
                skipped += 1
                print("skip", exc, flush=True)
                continue
            p = neighbours.placebo
            sub = plot.grid(0)
            col = int((sub.left - grid.left) / 10)
            row = int((grid.top - sub.top) / 10)
            vals = pre_full.ndvi[row: row + sub.height, col: col + sub.width][plot.stats_mask(sub)]
            vals = vals[np.isfinite(vals)]
            rec = dict(
                i=done, lon=round(lon, 6), lat=round(lat, 6), side_m=round(side, 1), area_ha=round(plot.area_ha, 3),
                pre_ndvi=optical.pre.ndvi_median, post_ndvi=optical.post.ndvi_median, delta=optical.plot_delta_ndvi,
                pre_iqr=round(float(np.subtract(*np.percentile(vals, [75, 25]))), 4) if vals.size else None,
                drop_frac=optical.drop_frac, pattern=optical.within_plot_pattern, bare=optical.post_bare_fraction,
                neighbour_delta=neighbours.neighbour_median_delta, n_placebos=p.n_placebos,
                n_non_overlapping=p.n_non_overlapping, p=p.p_value, k=p.n_at_least_as_extreme,
                placebo_median=p.placebo_median, placebo_p05=p.placebo_p05, placebo_p95=p.placebo_p95,
                ring_outer=neighbours.ring_m[1], insufficient=p.insufficient_reason,
            )
            out.write(json.dumps(rec) + "\n")
            out.flush()
            done += 1
            if done % 25 == 0:
                print(f"{done} plots, {(time.time() - t0) / done:.2f} s each", flush=True)
    print(f"done={done} skipped={skipped} attempts={attempts} seconds={time.time() - t0:.0f}", flush=True)


if __name__ == "__main__":
    main()

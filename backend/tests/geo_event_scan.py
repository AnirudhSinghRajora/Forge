"""Scan a documented event: random cropland plots through the unchanged engine. Real data; not a pytest.

Run from backend/:
  PYTHONPATH=. uv run python tests/geo_event_scan.py --lat 16.65 --lon 81.85 --s2-pre ID --s2-post ID \\
      [--s1-pre ID --s1-post ID] --n 200 --out results.jsonl

Every sampled plot is written out, so the distribution is reported and not only the best plot. Picking
the most extreme of N plots and quoting its p-value is selection; a report must say so.
"""
from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np
from pyproj import Transformer

from app.tools.geo.base import PlotError, SceneUnusable
from app.tools.geo.grid import Grid, parse_plot, utm_epsg
from app.tools.geo.optical import RED_EDGE_BANDS, _optical_compare
from app.tools.geo.qa import QA_BANDS
from app.tools.geo.raster import prefetch_region
from app.tools.geo.sar import _sar_compare
from tests.geo_fpr_sirsa import CROPLAND, MARGIN_PX, square, worldcover


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--size-px", type=int, default=1200)
    ap.add_argument("--s2-pre")
    ap.add_argument("--s2-post")
    ap.add_argument("--s1-pre")
    ap.add_argument("--s1-post")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    epsg = utm_epsg(args.lon, args.lat)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    to_ll = Transformer.from_crs(epsg, 4326, always_xy=True)
    x, y = to_utm.transform(args.lon, args.lat)
    half = args.size_px * 5
    grid = Grid(epsg, float(math.floor((x - half) / 10) * 10), float(math.ceil((y + half) / 10) * 10), args.size_px, args.size_px)

    t0 = time.time()
    if args.s2_pre and args.s2_post:
        prefetch_region([args.s2_pre, args.s2_post], QA_BANDS + RED_EDGE_BANDS, grid)
    if args.s1_pre and args.s1_post:
        prefetch_region([args.s1_pre, args.s1_post], ["vv", "vh"], grid, is_float=True)
    cover = worldcover(grid)
    print(f"region read in {time.time() - t0:.0f} s; cropland share {np.mean(cover == CROPLAND):.2f}", flush=True)

    rng = np.random.default_rng(args.seed)
    done = attempts = 0
    skipped: dict[str, int] = {}
    with open(args.out, "w") as out:
        while done < args.n and attempts < args.n * 60:
            attempts += 1
            side = float(rng.uniform(100.0, 141.4))
            hw = int(math.ceil(side / 20))
            r = int(rng.integers(MARGIN_PX, grid.height - MARGIN_PX))
            c = int(rng.integers(MARGIN_PX, grid.width - MARGIN_PX))
            if np.mean(cover[r - hw: r + hw, c - hw: c + hw] == CROPLAND) < 0.8:
                continue
            lon, lat = to_ll.transform(grid.left + (c + 0.5) * 10, grid.top - (r + 0.5) * 10)
            poly = square(lon, lat, side)
            if parse_plot(poly).epsg != epsg:
                continue
            rec: dict = dict(i=done, lon=round(lon, 6), lat=round(lat, 6), side_m=round(side, 1))
            try:
                if args.s2_pre and args.s2_post:
                    optical, neighbours = _optical_compare(poly, args.s2_pre, args.s2_post, seed=done, with_twin=False)
                    p = neighbours.placebo
                    rec.update(
                        pre_ndvi=optical.pre.ndvi_median, post_ndvi=optical.post.ndvi_median, delta=optical.plot_delta_ndvi,
                        drop_frac=optical.drop_frac, pattern=optical.within_plot_pattern, bare=optical.post_bare_fraction,
                        neighbour_delta=neighbours.neighbour_median_delta, neighbour_bare=neighbours.neighbour_bare_fraction_post,
                        n_placebos=p.n_placebos, p=p.p_value, placebo_median=p.placebo_median, insufficient=p.insufficient_reason,
                    )
            except (SceneUnusable, PlotError) as exc:
                skipped[str(exc)[:60]] = skipped.get(str(exc)[:60], 0) + 1
                rec["optical_skipped"] = str(exc)[:160]
            if args.s1_pre and args.s1_post:
                sar = _sar_compare(poly, args.s1_pre, args.s1_post, seed=done)
                rec.update(
                    sar_usable=sar.usable, vh_change=sar.vh_change_db, vh_neighbour=sar.neighbour_vh_change_db,
                    vh_excess=sar.vh_excess_db, new_water=sar.new_water_frac, water_pre=sar.water_frac_pre,
                    water_post=sar.water_frac_post, sar_p=sar.placebo.p_value if sar.placebo else None,
                    sar_n=sar.placebo.n_placebos if sar.placebo else None, sar_reason=sar.reason,
                    sar_insufficient=sar.placebo.insufficient_reason if sar.placebo else None,
                )
            out.write(json.dumps(rec) + "\n")
            out.flush()
            done += 1
            if done % 25 == 0:
                print(f"{done} plots ({time.time() - t0:.0f} s)", flush=True)
    print(f"done={done} attempts={attempts} seconds={time.time() - t0:.0f} optical_skips={skipped}", flush=True)


if __name__ == "__main__":
    main()

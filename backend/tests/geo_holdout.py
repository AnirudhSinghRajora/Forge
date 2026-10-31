"""Rubric v3 field conditions on a locked window. Real data; not a pytest. Runs once per window.

Applies the frozen rule from app/agent/rubric.py and cross_exam.py. Nothing here may be tuned after
seeing a result: any failure is reported, not fixed and re-run.

Plots: random squares on ESA WorldCover cropland in a central zone. The zone is read once along with
everything the far windows need, and each plot goes through the unchanged optical_compare.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import timedelta

import numpy as np
from pyproj import Transformer

import app.tools.geo.optical as optical_module
from app.agent.cross_exam import PRE_TREND_FALLING
from app.agent.rubric import MIN_PLACEBOS, MODERATE_DELTA, P_FIELD, STRONG_DELTA
from app.tools.geo.base import PlotError, SceneUnusable
from app.tools.geo.far import FAR_OUTER_M
from app.tools.geo.grid import Grid, parse_plot, utm_epsg
from app.tools.geo.optical import RED_EDGE_BANDS, TWIN_PRE_DAYS, _optical_compare
from app.tools.geo.qa import QA_BANDS
from app.tools.geo.raster import prefetch_region
from app.tools.geo.stac import get_scene, search_scenes
from tests.geo_fpr_sirsa import CROPLAND, square, worldcover

CENTRAL_M = 4000  # half-width of the zone plots are drawn from
CONTEXT_MARGIN_M = 1800
BLOCK_M = 5120


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--pre", required=True)
    ap.add_argument("--post", required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261101)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    epsg = utm_epsg(args.lon, args.lat)
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(args.lon, args.lat)
    to_ll = Transformer.from_crs(epsg, 4326, always_xy=True)

    def square_grid(half_m: float) -> Grid:
        size = int(2 * half_m / 10)
        return Grid(epsg, float(math.floor((x - half_m) / 10) * 10), float(math.ceil((y + half_m) / 10) * 10), size, size)

    wide = square_grid(CENTRAL_M + FAR_OUTER_M + BLOCK_M)
    near = square_grid(CENTRAL_M + CONTEXT_MARGIN_M)
    pre = get_scene(args.pre)
    post = get_scene(args.post)

    # One search per run. Plots in one tile see the same passes; this avoids 300 identical requests.
    centre = parse_plot(square(args.lon, args.lat, 120.0))
    listed = search_scenes("sentinel-2-l2a", centre, pre.date - timedelta(days=TWIN_PRE_DAYS), post.date)
    optical_module.search_scenes = lambda collection, plot, start, end: [s for s in listed if start <= s.date <= end]

    t0 = time.time()
    prefetch_region([pre.id, post.id], ["B04", "B08", "SCL"], wide)
    print(f"far region read in {time.time() - t0:.0f} s", flush=True)
    others = sorted((s for s in listed if s.date < pre.date), key=lambda s: s.datetime, reverse=True)
    others = [s for s in others if s.cloud_pct is None or s.cloud_pct <= optical_module.TWIN_MAX_TILE_CLOUD][:6]
    prefetch_region([pre.id, post.id], [b for b in QA_BANDS + RED_EDGE_BANDS if b not in ("B04", "B08", "SCL")], near)
    prefetch_region([s.id for s in others], ["B04", "B08", "SCL"], near)
    cover = worldcover(near)
    print(f"all regions read in {time.time() - t0:.0f} s; cropland {np.mean(cover == CROPLAND):.2f}", flush=True)

    rng = np.random.default_rng(args.seed)
    margin = int(CONTEXT_MARGIN_M / 10)
    done = attempts = 0
    skipped: dict[str, int] = {}
    t0 = time.time()
    with open(args.out, "w") as out:
        while done < args.n and attempts < args.n * 50:
            attempts += 1
            side = float(rng.uniform(100.0, 141.4))
            hw = int(math.ceil(side / 20))
            r = int(rng.integers(margin, near.height - margin))
            c = int(rng.integers(margin, near.width - margin))
            if np.mean(cover[r - hw: r + hw, c - hw: c + hw] == CROPLAND) < 0.8:
                continue
            lon, lat = to_ll.transform(near.left + (c + 0.5) * 10, near.top - (r + 0.5) * 10)
            poly = square(lon, lat, side)
            try:
                opt, nb = _optical_compare(poly, pre.id, post.id, seed=done)
            except (SceneUnusable, PlotError) as exc:
                key = str(exc)[:70]
                skipped[key] = skipped.get(key, 0) + 1
                continue

            def usable(test):
                if test is None or test.insufficient_reason or test.n_placebos < MIN_PLACEBOS:
                    return None
                return test.p_value

            ring_p, far_p = usable(nb.placebo), usable(nb.far_placebo)
            signal = (ring_p is not None and ring_p <= P_FIELD) or (far_p is not None and far_p <= P_FIELD)
            delta = opt.plot_delta_ndvi
            falling = nb.pretrend_delta is not None and nb.pretrend_delta <= PRE_TREND_FALLING
            rec = dict(
                i=done, lat=round(lat, 6), lon=round(lon, 6), side_m=round(side, 1), delta=delta,
                pre_ndvi=opt.pre.ndvi_median, post_ndvi=opt.post.ndvi_median, bare=opt.post_bare_fraction,
                pattern=opt.within_plot_pattern, neighbour_delta=nb.neighbour_median_delta,
                ring_p=ring_p, ring_n=nb.placebo.n_placebos, far_p=far_p, far_n=nb.far_placebo.n_placebos if nb.far_placebo else None,
                far_median=nb.far_placebo.placebo_median if nb.far_placebo else None,
                far_insufficient=nb.far_placebo.insufficient_reason if nb.far_placebo else None,
                ring_insufficient=nb.placebo.insufficient_reason, pretrend=nb.pretrend_delta,
                twin_gap=nb.counterfactual.gap_at_post if nb.counterfactual else None,
                signal=signal, falling=falling,
                strong_field=bool(signal and delta <= STRONG_DELTA and not falling),
                moderate_field=bool(signal and delta <= MODERATE_DELTA and not falling),
                strong_ignoring_pretrend=bool(signal and delta <= STRONG_DELTA),
                moderate_ignoring_pretrend=bool(signal and delta <= MODERATE_DELTA),
            )
            out.write(json.dumps(rec) + "\n")
            out.flush()
            done += 1
            if done % 25 == 0:
                print(f"{done} plots, {(time.time() - t0) / done:.1f} s each", flush=True)
    print(f"HOLDOUT_DONE done={done} attempts={attempts} seconds={time.time() - t0:.0f} skipped={skipped}", flush=True)


if __name__ == "__main__":
    main()

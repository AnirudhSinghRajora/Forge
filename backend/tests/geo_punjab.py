"""Pre-registered independent positive test: Punjab floods, Aug 2025. See engine-results.md section 7b.

Run once: PYTHONPATH=. uv run python tests/geo_punjab.py --out results.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date, timedelta

import numpy as np
import pystac_client
from pyproj import Transformer

from app.agent.cross_exam import PRE_TREND_FALLING
from app.agent.rubric import MIN_PLACEBOS, MODERATE_DELTA, P_FIELD, P_SAR, STRONG_DELTA
from app.tools.geo.base import STAC_URL, GeoUnavailable, PlotError, SceneUnusable
from app.tools.geo.grid import Grid, parse_plot, utm_epsg
from app.tools.geo.optical import _optical_compare, search_and_qa
from app.tools.geo.raster import _warped_once
from app.tools.geo.sar import _sar_compare, search_sar
from tests.geo_fpr_sirsa import CROPLAND, square

SITES = {"Pakhoke Mehmaran": (32.01496, 75.01210), "Dera Baba Nanak": (32.03325, 75.02517), "Kot Gurbaksh": (31.98063, 74.91547)}
PER_SITE = 20
RADIUS_M = 1500
SEED = 20250827
NEW_WATER = 0.2


def cover_at(lat: float, lon: float) -> tuple[np.ndarray, Grid]:
    """WorldCover around a site, merging tiles: these sites straddle the 75E tile edge."""
    epsg = utm_epsg(lon, lat)
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    half = RADIUS_M + 200
    size = int(2 * half / 10)
    grid = Grid(epsg, float(math.floor((x - half) / 10) * 10), float(math.ceil((y + half) / 10) * 10), size, size)
    w, s, e, n = grid.lonlat_bounds()
    cat = pystac_client.Client.open(STAC_URL)
    items = [i for i in cat.search(collections=["esa-worldcover"], bbox=[w, s, e, n]).items() if "2021" in i.id]
    merged = np.zeros(grid.shape, np.uint8)
    for item in items:
        layer = _warped_once(item.assets["map"].href, grid, False)
        merged = np.where(merged == 0, layer, merged)
    return merged, grid


def draw_plots() -> list[dict]:
    rng = np.random.default_rng(SEED)
    plots = []
    for site, (lat, lon) in SITES.items():
        cover, grid = cover_at(lat, lon)
        to_ll = Transformer.from_crs(grid.epsg, 4326, always_xy=True)
        centre_r, centre_c = grid.height // 2, grid.width // 2
        kept = 0
        while kept < PER_SITE:
            side = float(rng.uniform(100.0, 141.4))
            angle = float(rng.uniform(0, 2 * math.pi))
            dist = RADIUS_M * math.sqrt(float(rng.uniform(0, 1)))
            r = int(centre_r - dist * math.sin(angle) / 10)
            c = int(centre_c + dist * math.cos(angle) / 10)
            hw = int(math.ceil(side / 20))
            if np.mean(cover[r - hw: r + hw, c - hw: c + hw] == CROPLAND) < 0.8:
                continue
            plon, plat = to_ll.transform(grid.left + (c + 0.5) * 10, grid.top - (r + 0.5) * 10)
            plots.append(dict(i=len(plots), site=site, lat=round(plat, 6), lon=round(plon, 6), side_m=round(side, 1)))
            kept += 1
    return plots


def pick_radar(polygon: dict, year: int):
    before = date(year, 8, 26)
    after = date(year, 8, 27)
    scenes = search_sar(polygon, date(year, 7, 15), date(year, 10, 5))
    orbits: dict = {}
    for s in scenes:
        orbits.setdefault((s.relative_orbit, s.orbit_state), []).append(s)
    pairs = []
    for key, group in orbits.items():
        pre = [s for s in group if s.date < before]
        post = [s for s in group if s.date > after]
        if pre and post:
            a, b = max(pre, key=lambda s: s.datetime), min(post, key=lambda s: s.datetime)
            pairs.append(((b.date, (b.date - a.date).days, key[0]), a, b))
    return min(pairs, key=lambda p: p[0]) if pairs else None


def pick_optical(polygon: dict, year: int):
    event = date(year, 8, 27)
    found = search_and_qa(polygon, event - timedelta(days=30), event + timedelta(days=20))
    accepted = [s for s, q in found if q.status == "accepted"]
    pre = [s for s in accepted if s.date < date(year, 8, 26)]
    post_all = [s for s in accepted if s.date > event]
    post = [s for s in post_all if (s.date - event).days >= 5] or post_all
    return (max(pre, key=lambda s: s.datetime) if pre else None, min(post, key=lambda s: s.datetime) if post else None, len(found))


def usable(test):
    if test is None or test.insufficient_reason or test.n_placebos < MIN_PLACEBOS:
        return None
    return test.p_value


def run_plot(plot: dict, year: int) -> dict:
    polygon = square(plot["lon"], plot["lat"], plot["side_m"])
    parse_plot(polygon)
    rec = dict(plot, year=year)
    pair = pick_radar(polygon, year)
    if pair is None:
        rec["radar"] = "no same-orbit pair"
    else:
        _, a, b = pair
        sar = _sar_compare(polygon, a.id, b.id, seed=plot["i"])
        p = usable(sar.placebo)
        rec.update(
            radar="ok" if sar.usable else f"unusable: {sar.reason}", sar_pre=a.id, sar_post=b.id, sar_pre_date=str(a.date),
            sar_post_date=str(b.date), orbit=a.relative_orbit, direction=a.orbit_state, new_water=sar.new_water_frac,
            water_pre=sar.water_frac_pre, water_post=sar.water_frac_post, vh_change=sar.vh_change_db,
            vh_neighbour=sar.neighbour_vh_change_db, sar_p=p, sar_reason=sar.reason,
            sar_field=bool(sar.usable and ((p is not None and p <= P_SAR) or (sar.new_water_frac or 0) >= NEW_WATER)),
        )
    pre, post, n_found = pick_optical(polygon, year)
    rec.update(optical_scenes_found=n_found, optical_pre=pre.id if pre else None, optical_post=post.id if post else None)
    if pre and post:
        try:
            opt, nb = _optical_compare(polygon, pre.id, post.id, seed=plot["i"])
            ring, far = usable(nb.placebo), usable(nb.far_placebo)
            signal = (ring is not None and ring <= P_FIELD) or (far is not None and far <= P_FIELD)
            falling = nb.pretrend_delta is not None and nb.pretrend_delta <= PRE_TREND_FALLING
            delta = opt.plot_delta_ndvi
            rec.update(
                delta=delta, pre_ndvi=opt.pre.ndvi_median, post_ndvi=opt.post.ndvi_median, bare=opt.post_bare_fraction,
                ring_p=ring, far_p=far, pretrend=nb.pretrend_delta, signal=signal,
                strong_field=bool(signal and delta <= STRONG_DELTA and not falling),
                moderate_field=bool(signal and delta <= MODERATE_DELTA and not falling),
            )
        except (SceneUnusable, PlotError) as exc:
            rec["optical_error"] = str(exc)[:160]
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    t0 = time.time()
    plots = draw_plots()
    print(f"{len(plots)} plots drawn in {time.time() - t0:.0f} s", flush=True)
    with open(args.out, "w") as out:
        for year in (2025, 2024):
            for plot in plots:
                try:
                    rec = run_plot(plot, year)
                except GeoUnavailable as exc:
                    rec = dict(plot, year=year, outage=str(exc)[:200])
                out.write(json.dumps(rec) + "\n")
                out.flush()
                if plot["i"] % 10 == 9:
                    print(f"{year}: {plot['i'] + 1} plots, {time.time() - t0:.0f} s", flush=True)
    print("PUNJAB_DONE", flush=True)


if __name__ == "__main__":
    main()

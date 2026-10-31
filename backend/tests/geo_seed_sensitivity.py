"""How much do placebo p-values move with the seed alone? Same data, same method. Not a pytest.

Plots: the two demo plots, plus the 5 in-band plots whose far p (seed = their index in the in-band set)
falls closest to the 0.025 line, chosen by that rule. Each runs across 30 seeds.
Field levels use rubric v3's rule assuming corroboration is present: strong = delta <= -0.15 with a field
signal, moderate = delta <= -0.10 with a field signal, weak otherwise. Pre-trend is left out, because it
does not depend on the far or ring placement and was flat on the demo plots.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import Counter

import numpy as np
from pyproj import Transformer

from app.agent.rubric import MIN_PLACEBOS, MODERATE_DELTA, P_FIELD, STRONG_DELTA
from app.tools.geo.far import FAR_OUTER_M
from app.tools.geo.grid import Grid, utm_epsg
from app.tools.geo.optical import RED_EDGE_BANDS, _optical_compare
from app.tools.geo.qa import QA_BANDS
from app.tools.geo.raster import prefetch_region
from tests.geo_fpr_sirsa import square

PRE = "S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503"
POST = "S2B_MSIL2A_20240309T052639_R105_T43RFM_20240309T092738"
LAT, LON = 28.72, 76.21
CENTRAL_M = 6000
BLOCK_M = 5120
DEMOS = [("extreme (strongest of 200)", 28.700911, 76.215719, 113.1), ("typical (median of 40)", 28.715212, 76.231138, 104.7)]


def run(lat: float, lon: float, side: float, seed: int) -> dict:
    opt, nb = _optical_compare(square(lon, lat, side), PRE, POST, seed=seed, with_twin=False)

    def usable(test):
        if test is None or test.insufficient_reason or test.n_placebos < MIN_PLACEBOS:
            return None
        return test.p_value

    ring_p, far_p = usable(nb.placebo), usable(nb.far_placebo)
    signal = (ring_p is not None and ring_p <= P_FIELD) or (far_p is not None and far_p <= P_FIELD)
    delta = opt.plot_delta_ndvi
    level = "strong" if signal and delta <= STRONG_DELTA else "moderate" if signal and delta <= MODERATE_DELTA else "weak"
    return dict(
        seed=seed, delta=delta, ring_p=ring_p, far_p=far_p, ring_n=nb.placebo.n_placebos,
        far_n=nb.far_placebo.n_placebos if nb.far_placebo else None, signal=signal, level=level,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--band", required=True, help="the in-band jsonl from geo_band_distribution.py")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--near", type=int, default=5)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    epsg = utm_epsg(LON, LAT)
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(LON, LAT)

    def square_grid(half_m: float) -> Grid:
        size = int(2 * half_m / 10)
        return Grid(epsg, float(math.floor((x - half_m) / 10) * 10), float(math.ceil((y + half_m) / 10) * 10), size, size)

    t0 = time.time()
    prefetch_region([PRE, POST], ["B04", "B08", "SCL"], square_grid(CENTRAL_M + FAR_OUTER_M + BLOCK_M))
    prefetch_region(
        [PRE, POST], [b for b in QA_BANDS + RED_EDGE_BANDS if b not in ("B04", "B08", "SCL")], square_grid(CENTRAL_M + 1800)
    )
    print(f"regions read in {time.time() - t0:.0f} s", flush=True)

    band = [json.loads(line) for line in open(args.band)]
    candidates = []
    for row in band:
        if abs(row["lat"] - LAT) * 111000 > CENTRAL_M or abs(row["lon"] - LON) * 97000 > CENTRAL_M:
            continue
        rec = run(row["lat"], row["lon"], row["side_m"], row["i"])
        if rec["far_p"] is not None:
            candidates.append((abs(rec["far_p"] - P_FIELD), row, rec))
    candidates.sort(key=lambda c: (c[0], c[1]["i"]))
    print(f"{len(candidates)} of {len(band)} in-band plots eligible; far p at their own seed: "
          f"{np.round(np.percentile([c[2]['far_p'] for c in candidates], [0, 25, 50, 75, 100]), 4).tolist()}; "
          f"signal on {sum(1 for c in candidates if c[2]['signal'])}", flush=True)

    plots = list(DEMOS)
    for _, row, _ in candidates[: args.near]:
        plots.append((f"near line, in-band #{row['i']}", row["lat"], row["lon"], row["side_m"]))

    seeds = [int(s) for s in np.random.default_rng(20261101).integers(1, 2**31 - 1, args.seeds)]
    with open(args.out, "w") as out:
        for name, lat, lon, side in plots:
            rows = [run(lat, lon, side, seed) for seed in seeds]
            far = np.array([np.nan if r["far_p"] is None else r["far_p"] for r in rows])
            ring = np.array([np.nan if r["ring_p"] is None else r["ring_p"] for r in rows])
            levels = Counter(r["level"] for r in rows)
            top = levels.most_common(1)[0][1]
            summary = dict(
                plot=name, lat=lat, lon=lon, side_m=side, delta=rows[0]["delta"], n_seeds=len(rows),
                far_min=float(np.nanmin(far)), far_median=float(np.nanmedian(far)), far_max=float(np.nanmax(far)),
                ring_min=float(np.nanmin(ring)), ring_median=float(np.nanmedian(ring)), ring_max=float(np.nanmax(ring)),
                far_n=[min(r["far_n"] for r in rows), max(r["far_n"] for r in rows)],
                ring_n=[min(r["ring_n"] for r in rows), max(r["ring_n"] for r in rows)],
                far_sig_share=float(np.nanmean(far <= P_FIELD)), ring_sig_share=float(np.nanmean(ring <= P_FIELD)),
                signal_share=float(np.mean([r["signal"] for r in rows])),
                levels=dict(levels), level_differs_from_majority=1 - top / len(rows),
                rows=rows,
            )
            out.write(json.dumps(summary) + "\n")
            out.flush()
            print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in summary.items() if k != "rows"}), flush=True)
    print("SEEDS_DONE", flush=True)


if __name__ == "__main__":
    main()

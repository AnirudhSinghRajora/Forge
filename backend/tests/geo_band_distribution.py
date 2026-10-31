"""The Draw and the Vanishing across in-band Bhiwani plots, chosen by rule. Real data; not a pytest.

Rule, fixed before looking: plot centres drawn uniformly at random from the band mask (smoothed
28 Feb -> 9 Mar 2024 change <= -0.12, from geo_c1_controls), at least 80% WorldCover cropland, pre NDVI
at least 0.5. The typical plot is the one whose plot change is the median of the set.
"""
from __future__ import annotations

import argparse
import json
import math
import time

import numpy as np
from PIL import Image
from pyproj import Transformer

from app.tools.geo.base import SceneUnusable, var_dir
from app.tools.geo.grid import Grid, parse_plot, utm_epsg
from app.tools.geo.optical import RED_EDGE_BANDS
from app.tools.geo.qa import QA_BANDS
from app.tools.geo.raster import prefetch_region
from app.tools.geo.scale import _scale_fade
from app.tools.geo.village import _village_witness
from tests.geo_fpr_sirsa import CROPLAND, square, worldcover

LAT, LON, SIZE = 28.735, 76.205, 1400
PRE = "S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503"
POST = "S2B_MSIL2A_20240309T052639_R105_T43RFM_20240309T092738"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=20261101)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    epsg = utm_epsg(LON, LAT)
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(LON, LAT)
    half = SIZE * 5
    grid = Grid(epsg, float(math.floor((x - half) / 10) * 10), float(math.ceil((y + half) / 10) * 10), SIZE, SIZE)
    to_ll = Transformer.from_crs(epsg, 4326, always_xy=True)
    prefetch_region([PRE, POST], QA_BANDS + RED_EDGE_BANDS, grid)
    cover = worldcover(grid)
    band = np.array(Image.open(var_dir() / "geo_validation" / "c1_controls" / "swath_mask.png")) > 127
    margin = 320  # keeps the 3 km village window inside the prefetched region
    allowed = np.zeros(band.shape, bool)
    allowed[margin:-margin, margin:-margin] = True
    rows, cols = np.nonzero(band & allowed)
    print(f"band pixels available {rows.size}", flush=True)
    rng = np.random.default_rng(args.seed)
    order = rng.permutation(rows.size)
    done = tried = skipped = 0
    t0 = time.time()
    with open(args.out, "w") as out:
        for index in order:
            if done >= args.n:
                break
            tried += 1
            r, c = int(rows[index]), int(cols[index])
            side = float(rng.uniform(100.0, 141.4))
            hw = int(math.ceil(side / 20))
            if np.mean(cover[r - hw: r + hw, c - hw: c + hw] == CROPLAND) < 0.8:
                continue
            lon, lat = to_ll.transform(grid.left + (c + 0.5) * 10, grid.top - (r + 0.5) * 10)
            poly = square(lon, lat, side)
            parse_plot(poly)
            try:
                village = _village_witness(poly, PRE, POST, done, "s2")
                fade = _scale_fade(poly, PRE, POST, None, "s2")
            except SceneUnusable:
                skipped += 1
                continue
            lot = village.lottery
            rec = dict(
                i=done, lat=round(lat, 6), lon=round(lon, 6), side_m=round(side, 1), plot_value=lot.plot_value,
                affected_share=village.affected_share, n_candidates=lot.n_candidate_parcels,
                insufficient=lot.insufficient_reason, draw_median=lot.average_median, draw_p05=lot.average_p05,
                draw_p95=lot.average_p95, share_below_half=lot.share_below_half_of_plot,
                only_n=lot.affected_only_n_candidates, only_median=lot.affected_only_median,
                only_p05=lot.affected_only_p05, only_p95=lot.affected_only_p95, only_reason=lot.affected_only_reason,
                fade={str(level.block_m): level.plot_cell_value for level in fade.levels},
            )
            out.write(json.dumps(rec) + "\n")
            out.flush()
            done += 1
            if done % 10 == 0:
                print(f"{done} plots, {(time.time() - t0) / done:.1f} s each", flush=True)
    print(f"DISTRIBUTION_DONE done={done} tried={tried} skipped={skipped}", flush=True)


if __name__ == "__main__":
    main()

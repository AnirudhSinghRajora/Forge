"""Every number on both demo plots, to compare one engine build against another. Not a pytest.

PYTHONPATH=. uv run python tests/geo_baseline.py --out numbers.json
FASALSAAKSHI_VAR_DIR can point at an empty directory, to force every read to be cold.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date

from app.tools import geo
from tests.geo_fpr_sirsa import square

PRE = "S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503"
POST = "S2B_MSIL2A_20240309T052639_R105_T43RFM_20240309T092738"
S1_PRE = "S1A_IW_GRDH_1SDV_20240222T130339_20240222T130404_052672_065F66_rtc"
S1_POST = "S1A_IW_GRDH_1SDV_20240305T130339_20240305T130404_052847_06655A_rtc"
EVENT = date(2024, 3, 3)
PLOTS = {"extreme": (76.215719, 28.700911, 113.1), "typical": (76.231138, 28.715212, 104.7)}
SEED = 7


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result: dict = {"engine": geo.ENGINE_VERSION, "plots": {}, "timings": {}}
    for name, (lon, lat, side) in PLOTS.items():
        polygon = square(lon, lat, side)
        timings = {}

        def step(label, fn):
            t0 = time.time()
            value = fn()
            timings[label] = round(time.time() - t0, 1)
            print(name, label, timings[label], flush=True)
            return value

        optical, neighbours = step("optical_compare", lambda: geo.optical_compare(polygon, PRE, POST, SEED))
        sar = step("sar_compare", lambda: geo.sar_compare(polygon, S1_PRE, S1_POST, SEED))
        hist = step("history", lambda: geo.history(
            polygon, EVENT, current_delta=optical.plot_delta_ndvi, current_pre_ndvi=optical.pre.ndvi_median,
        ))
        village = step("village_witness", lambda: geo.village_witness(polygon, PRE, POST, SEED, "s2"))
        fade = step("scale_fade", lambda: _fade(polygon))
        result["plots"][name] = geo.flatten_numbers(optical, neighbours, sar, hist, village, fade)
        result["timings"][name] = timings
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=0, sort_keys=True)
    print("BASELINE_DONE", {k: len(v) for k, v in result["plots"].items()}, flush=True)


def _fade(polygon):
    from app.tools.geo.scale import _scale_fade

    return _scale_fade(polygon, PRE, POST, None, "s2")


if __name__ == "__main__":
    main()

"""Attack the Bhiwani band: is it hail, or a soil and crop pattern that recurs every year?

The swath mask is defined once from the 28 Feb -> 9 Mar 2024 map. Every other pair is out of sample.
PYTHONPATH=. uv run python tests/geo_c1_controls.py
"""
from __future__ import annotations

import json
import math

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy import ndimage

from app.tools.geo import indices as ix
from app.tools.geo.base import var_dir
from app.tools.geo.chips import DELTA_RANGE, _colourise
from app.tools.geo.grid import Grid, utm_epsg
from app.tools.geo.raster import read_assets
from app.tools.geo.sar import to_db
from app.tools.geo.stac import get_scene

LAT, LON, SIZE = 28.735, 76.205, 1400
GREEN = 0.5
PAIRS = [
    ("EVENT 2024-02-28 -> 03-09", "S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503", "S2B_MSIL2A_20240309T052639_R105_T43RFM_20240309T092738"),
    ("event 2024-02-28 -> 03-04 (1-2 days after hail)", "S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503", "S2A_MSIL2A_20240304T052721_R105_T43RFM_20240304T111934"),
    ("event 2024-02-28 -> 03-14", "S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503", "S2A_MSIL2A_20240314T052641_R105_T43RFM_20240314T104206"),
    ("before 2024-02-23 -> 02-28 (no hail yet)", "S2A_MSIL2A_20240223T052831_R105_T43RFM_20240223T103922", "S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503"),
    ("other year 2022-02-28 -> 03-10", "S2B_MSIL2A_20220228T052749_R105_T43RFM_20220303T034744", "S2B_MSIL2A_20220310T052649_R105_T43RFM_20220311T052945"),
    ("other year 2023-02-23 -> 03-05", "S2B_MSIL2A_20230223T052829_R105_T43RFM_20230223T215223", "S2B_MSIL2A_20230305T052719_R105_T43RFM_20240819T183418"),
    ("other year 2023-03-05 -> 03-10", "S2B_MSIL2A_20230305T052719_R105_T43RFM_20240819T183418", "S2A_MSIL2A_20230310T052641_R105_T43RFM_20240824T200443"),
    ("other year 2025-03-04 -> 03-14", "S2B_MSIL2A_20250304T052649_R105_T43RFM_20250304T073919", "S2B_MSIL2A_20250314T052649_R105_T43RFM_20250314T095315"),
]
RADAR = [
    ("radar VH 2024-02-22 -> 03-05 asc 100", "S1A_IW_GRDH_1SDV_20240222T130339_20240222T130404_052672_065F66_rtc", "S1A_IW_GRDH_1SDV_20240305T130339_20240305T130404_052847_06655A_rtc"),
    ("radar VH 2024-02-25 -> 03-08 desc 136", "S1A_IW_GRDH_1SDV_20240225T005232_20240225T005257_052708_06609F_rtc", "S1A_IW_GRDH_1SDV_20240308T005232_20240308T005257_052883_066693_rtc"),
]


def ndvi_layer(scene_id: str, grid: Grid, post: bool) -> tuple[np.ndarray, np.ndarray]:
    scene = get_scene(scene_id)
    b = read_assets(scene_id, ["B04", "B08", "SCL"], grid)
    off = ix.boa_offset(scene.processing_baseline)
    vi = ix.ndvi(ix.to_reflectance(b["B08"], off), ix.to_reflectance(b["B04"], off))
    vi[~ix.clear_mask(b["SCL"], allow_water=post)] = np.nan
    return vi, b["SCL"]


def main() -> None:
    epsg = utm_epsg(LON, LAT)
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(LON, LAT)
    half = SIZE * 5
    grid = Grid(epsg, float(math.floor((x - half) / 10) * 10), float(math.ceil((y + half) / 10) * 10), SIZE, SIZE)
    out_dir = var_dir() / "geo_validation" / "c1_controls"
    out_dir.mkdir(parents=True, exist_ok=True)

    a, _ = ndvi_layer(PAIRS[0][1], grid, False)
    b, _ = ndvi_layer(PAIRS[0][2], grid, True)
    d = b - a
    filled = np.where(np.isfinite(d) & (a >= GREEN), d, 0.0)
    weight = (np.isfinite(d) & (a >= GREEN)).astype(float)
    smooth = ndimage.gaussian_filter(filled, 30) / np.maximum(ndimage.gaussian_filter(weight, 30), 1e-3)
    swath = smooth <= -0.12
    ring = ndimage.binary_dilation(swath, iterations=100) & ~ndimage.binary_dilation(swath, iterations=30)
    far = ~ndimage.binary_dilation(swath, iterations=100)
    print(f"swath covers {swath.mean():.1%} of {SIZE * 10 / 1000:.0f} km window; near-ring {ring.mean():.1%}; far {far.mean():.1%}", flush=True)
    Image.fromarray((swath * 255).astype(np.uint8)).save(out_dir / "swath_mask.png")

    rows = []
    for name, pre_id, post_id in PAIRS:
        p, _ = ndvi_layer(pre_id, grid, False)
        q, _ = ndvi_layer(post_id, grid, True)
        delta = q - p
        green = p >= GREEN
        def med(mask):
            v = delta[mask & green & np.isfinite(delta)]
            return float(np.median(v)) if v.size else None
        def share(mask):
            v = delta[mask & green & np.isfinite(delta)]
            return float(np.mean(v <= -0.15)) if v.size else None
        def lev(mask):
            v = p[mask & np.isfinite(p)]
            return float(np.median(v)) if v.size else None
        row = dict(pair=name, inside=med(swath), near=med(ring), far=med(far), contrast_far=None, share_drop_inside=share(swath), share_drop_far=share(far),
                   pre_inside=lev(swath), pre_far=lev(far), valid=float(np.isfinite(delta).mean()))
        if row["inside"] is not None and row["far"] is not None:
            row["contrast_far"] = row["inside"] - row["far"]
        rows.append(row)
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
        safe = name.split("(")[0].strip().replace(" ", "_").replace(">", "").replace("-", "")
        Image.fromarray(_colourise(delta, "RdBu", -DELTA_RANGE, DELTA_RANGE), "RGB").save(out_dir / f"{safe}.png")

    for name, pre_id, post_id in RADAR:
        va = read_assets(pre_id, ["vh"], grid, is_float=True)["vh"]
        vb = read_assets(post_id, ["vh"], grid, is_float=True)["vh"]
        change = to_db(vb) - to_db(va)
        row = dict(pair=name, inside=float(np.nanmedian(change[swath])), near=float(np.nanmedian(change[ring])), far=float(np.nanmedian(change[far])))
        row["contrast_far"] = row["inside"] - row["far"]
        rows.append(row)
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
    (out_dir / "controls.json").write_text(json.dumps(rows, indent=1))
    print("CONTROLS_DONE", flush=True)


if __name__ == "__main__":
    main()

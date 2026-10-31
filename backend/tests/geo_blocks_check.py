"""The block reader must equal the WarpedVRT reader, pixel for pixel, on real data. Not a pytest.

PYTHONPATH=. uv run python tests/geo_blocks_check.py
"""
from __future__ import annotations

import numpy as np

from app.tools.geo.grid import parse_plot
from app.tools.geo.raster import _warped_once, read_many
from app.tools.geo.stac import asset_href, get_item
from tests.geo_fpr_sirsa import square

CASES = [
    ("S2B_MSIL2A_20240228T052749_R105_T43RFM_20240228T091503", ["B04", "SCL", "B11"], False, (76.215719, 28.700911)),
    ("S1A_IW_GRDH_1SDV_20240222T130339_20240222T130404_052672_065F66_rtc", ["vh"], True, (76.215719, 28.700911)),
    ("S2C_44QND_20261031_0_L2A", ["B04", "SCL"], False, (81.97, 16.93)),
]

for item_id, assets, is_float, (lon, lat) in CASES:
    grid = parse_plot(square(lon, lat, 120.0)).grid()
    for asset in assets:
        got = read_many([(item_id, asset)], grid, is_float=is_float, fresh=True)[item_id][asset]
        want = _warped_once(asset_href(get_item(item_id), asset), grid, is_float)
        same = np.array_equal(got, want, equal_nan=is_float)
        print(item_id[:40], asset, "identical" if same else "DIFFERENT", got.shape, flush=True)
        assert same, (item_id, asset)
print("BLOCKS_CHECK_OK", flush=True)

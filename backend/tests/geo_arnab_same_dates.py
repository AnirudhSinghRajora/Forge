"""Do these same plots fall this much over these same days in other years? Real data; not a pytest.

PYTHONPATH=. uv run python tests/geo_arnab_same_dates.py scan.jsonl PRE_2026_DATE_LABEL
"""
from __future__ import annotations

import json
import sys

import numpy as np

from app.tools.geo import indices as ix
from app.tools.geo.grid import parse_plot
from app.tools.geo.raster import read_many
from app.tools.geo.stac import get_scene
from tests.geo_fpr_sirsa import square

CONTROLS = {
    "2024 26 to 31 Oct": ("S2B_MSIL2A_20241026T045819_R119_T44QND_20241026T080431", "S2A_MSIL2A_20241031T045941_R119_T44QND_20241031T090153"),
    "2023 27 Oct to 1 Nov": ("S2A_MSIL2A_20231027T045911_R119_T44QND_20241108T093400", "S2B_MSIL2A_20231101T045939_R119_T44QND_20231101T092007"),
}


def plot_delta(polygon: dict, pre_id: str, post_id: str):
    plot = parse_plot(polygon)
    grid = plot.grid(30)
    mask = plot.stats_mask(grid)
    pre, post = get_scene(pre_id), get_scene(post_id)
    bands = read_many([(s.id, b) for s in (pre, post) for b in ("B04", "B08", "SCL")], grid)

    def layer(scene, allow_water):
        got = bands[scene.id]
        off = ix.scene_offset(scene.processing_baseline, scene.boa_offset_applied)
        vi = ix.ndvi(ix.to_reflectance(got["B08"], off), ix.to_reflectance(got["B04"], off))
        vi[~ix.clear_mask(got["SCL"], allow_water=allow_water)] = np.nan
        return vi

    a, b = layer(pre, False), layer(post, True)
    both = mask & np.isfinite(a) & np.isfinite(b)
    if both.sum() < 0.8 * mask.sum():
        return None, None
    return float(np.median((b - a)[both])), float(np.median(a[both]))


rows = [json.loads(x) for x in open(sys.argv[1])]
rows = [r for r in rows if r.get("delta") is not None]
print(f"{len(rows)} plots usable in 2026")
out = {}
for name, (pre_id, post_id) in CONTROLS.items():
    deltas = []
    for r in rows:
        d, pre_ndvi = plot_delta(square(r["lon"], r["lat"], r["side_m"]), pre_id, post_id)
        deltas.append((r, d, pre_ndvi))
    usable = [(r, d, p) for r, d, p in deltas if d is not None]
    out[name] = usable
    this = np.array([r["delta"] for r, _, _ in usable])
    other = np.array([d for _, d, _ in usable])
    print(f"{name}: clear on {len(usable)} of {len(rows)}")
    if usable:
        print(f"  median change, same plots: 2026 {np.median(this):.3f}, {name[:4]} {np.median(other):.3f}; paired median difference {np.median(this - other):+.3f}")
        print(f"  share <= -0.15: 2026 {np.mean(this <= -.15):.1%}, {name[:4]} {np.mean(other <= -.15):.1%}; share <= -0.30: 2026 {np.mean(this <= -.30):.1%}, {name[:4]} {np.mean(other <= -.30):.1%}")
for r in sorted(rows, key=lambda r: r["delta"])[:6]:
    parts = []
    for name, usable in out.items():
        match = next(((d, p) for x, d, p in usable if x is r), None)
        parts.append(f"{name[:4]}: {match[0]:+.3f} (pre {match[1]:.2f})" if match else f"{name[:4]}: not clear")
    print(f"  {r['lat']},{r['lon']} 2026 {r['delta']:+.3f} (pre {r['pre_ndvi']:.2f}) ring p {r['p']} | " + "; ".join(parts))
print("SAME_DATES_DONE")

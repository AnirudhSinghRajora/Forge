"""Summarise a locked window: python tests/geo_holdout_report.py results.jsonl"""
from __future__ import annotations

import json
import sys

import numpy as np

from tests.geo_fpr_report import wilson  # noqa: E402


def show(name: str, rows: list[dict]) -> None:
    n = len(rows)
    if not n:
        print(f"{name}: none")
        return
    def rate(key):
        k = sum(1 for r in rows if r[key])
        lo, hi = wilson(k, n)
        return f"{k}/{n} = {k / n:.1%} (CI {lo:.1%}-{hi:.1%})"
    ring = np.array([r["ring_p"] for r in rows if r["ring_p"] is not None])
    far = np.array([r["far_p"] for r in rows if r["far_p"] is not None])
    print(f"{name}")
    print(f"  strong field conditions: {rate('strong_field')}")
    print(f"  moderate field conditions: {rate('moderate_field')}")
    print(f"  without the pre-trend check: strong {rate('strong_ignoring_pretrend')}; moderate {rate('moderate_ignoring_pretrend')}")
    print(f"  field signal (either test p<=0.025, any delta): {rate('signal')}; pre-trend falling: {rate('falling')}")
    if ring.size:
        print(f"  ring p: n={ring.size} p<=.025 {np.mean(ring <= .025):.1%} p<=.05 {np.mean(ring <= .05):.1%} deciles {np.histogram(ring, bins=np.linspace(0, 1, 11))[0].tolist()}")
    if far.size:
        print(f"  far p: n={far.size} p<=.025 {np.mean(far <= .025):.1%} p<=.05 {np.mean(far <= .05):.1%} deciles {np.histogram(far, bins=np.linspace(0, 1, 11))[0].tolist()}")
    d = np.array([r["delta"] for r in rows])
    print(f"  delta p5,50,95 {np.round(np.percentile(d, [5, 50, 95]), 3).tolist()}; share <=-.15 {np.mean(d <= -.15):.1%}; <=-.10 {np.mean(d <= -.10):.1%}")


rows = [json.loads(x) for x in open(sys.argv[1])]
insufficient = sum(1 for r in rows if r["far_insufficient"]), sum(1 for r in rows if r["ring_insufficient"])
print(f"plots {len(rows)}; far insufficient {insufficient[0]}; ring insufficient {insufficient[1]}")
show("all cropland", rows)
show("standing crop (pre NDVI >= 0.4)", [r for r in rows if r["pre_ndvi"] >= 0.4])

"""Summarise FPR results: python tests/geo_fpr_report.py results.jsonl"""
from __future__ import annotations

import json
import math
import sys

import numpy as np


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def line(name: str, rows: list[dict]) -> None:
    usable = [r for r in rows if not r["insufficient"]]
    n = len(usable)
    if not n:
        print(f"{name}: none usable (of {len(rows)})")
        return
    p = np.array([r["p"] for r in usable])
    k5, k10 = int((p <= 0.05).sum()), int((p <= 0.10).sum())
    lo5, hi5 = wilson(k5, n)
    lo10, hi10 = wilson(k10, n)
    dec = np.histogram(p, bins=np.linspace(0, 1, 11))[0].tolist()
    print(f"{name}: n={n} of {len(rows)}  p<=.05 {k5} ({k5 / n:.1%}, CI {lo5:.1%}-{hi5:.1%})  "
          f"p<=.10 {k10} ({k10 / n:.1%}, CI {lo10:.1%}-{hi10:.1%})  deciles {dec}  "
          f"median delta {np.median([r['delta'] for r in usable]):.3f}  mean placebos {np.mean([r['n_placebos'] for r in usable]):.0f}")


rows = [json.loads(x) for x in open(sys.argv[1])]
line("all cropland", rows)
line("standing crop (pre NDVI >= 0.4)", [r for r in rows if r["pre_ndvi"] >= 0.4])
line("bare before (pre NDVI < 0.3)", [r for r in rows if r["pre_ndvi"] < 0.3])
line("homogeneous (pre IQR < 0.08)", [r for r in rows if r["pre_iqr"] is not None and r["pre_iqr"] < 0.08])
line("standing + homogeneous", [r for r in rows if r["pre_ndvi"] >= 0.4 and r["pre_iqr"] is not None and r["pre_iqr"] < 0.08])
big = [r for r in rows if r["delta"] <= -0.15]
line("dropped >= 0.15", big)
print("share of all plots with delta <= -0.15:", round(len(big) / max(1, len(rows)), 3))

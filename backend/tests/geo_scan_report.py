"""Summarise an event scan: python tests/geo_scan_report.py scan.jsonl"""
from __future__ import annotations

import json
import sys

import numpy as np

rows = [json.loads(x) for x in open(sys.argv[1])]
opt = [r for r in rows if r.get("delta") is not None and not r.get("insufficient")]
print(f"plots {len(rows)}; optical usable {len(opt)}; skipped {sum(1 for r in rows if 'optical_skipped' in r)}")
if opt:
    d = np.array([r["delta"] for r in opt])
    p = np.array([r["p"] for r in opt])
    green = [r for r in opt if r["pre_ndvi"] >= 0.5]
    print("delta p5,25,50,75,95:", np.round(np.percentile(d, [5, 25, 50, 75, 95]), 3).tolist(), "pre NDVI median", np.median([r["pre_ndvi"] for r in opt]))
    print(f"p<=.05 {np.mean(p <= .05):.1%}  p<=.10 {np.mean(p <= .10):.1%}  delta<=-.15 {np.mean(d <= -.15):.1%}  delta<=-.15 & p<=.05 {np.mean((d <= -.15) & (p <= .05)):.1%}")
    print("p deciles", np.histogram(p, bins=np.linspace(0, 1, 11))[0].tolist())
    print("median neighbour delta", np.nanmedian([r["neighbour_delta"] for r in opt if r["neighbour_delta"] is not None]))
    print("patterns", {k: sum(1 for r in opt if r["pattern"] == k) for k in ("patchy", "uniform", "none")}, "bare median", np.median([r["bare"] for r in opt]))
    if green:
        dg = np.array([r["delta"] for r in green]); print(f"green-before plots n={len(green)} delta p5,50,95 {np.round(np.percentile(dg, [5, 50, 95]), 3).tolist()}")
    print("strongest by delta (selection: most extreme of the sample):")
    for r in sorted(opt, key=lambda r: r["delta"])[:8]:
        print("  ", r["lat"], r["lon"], "side", r["side_m"], "pre", r["pre_ndvi"], "post", r["post_ndvi"], "delta", r["delta"], "p", r["p"], "bare", r["bare"], r["pattern"], "nbr", r["neighbour_delta"])
sar = [r for r in rows if r.get("sar_usable")]
if sar:
    v = np.array([r["vh_change"] for r in sar]); sp = np.array([r["sar_p"] for r in sar]); w = np.array([r["new_water"] for r in sar])
    print(f"radar usable {len(sar)}: VH change p5,50,95 {np.round(np.percentile(v, [5, 50, 95]), 2).tolist()} dB; neighbour median {np.median([r['vh_neighbour'] for r in sar]):.2f}; p<=.05 {np.mean(sp <= .05):.1%}; p<=.10 {np.mean(sp <= .10):.1%}; new water >= 0.2 {np.mean(w >= .2):.1%}; median new water {np.median(w):.3f}")
    print("radar deciles", np.histogram(sp, bins=np.linspace(0, 1, 11))[0].tolist(), "| reason sample:", sar[0]["sar_reason"])

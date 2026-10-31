"""Score the Punjab test by the rules fixed in engine-results.md section 7b."""
from __future__ import annotations

import json
import sys
from collections import Counter

import numpy as np

rows = [json.loads(x) for x in open(sys.argv[1])]
years = {y: [r for r in rows if r["year"] == y] for y in (2025, 2024)}
parts = {}
for year, group in years.items():
    radar = [r for r in group if r.get("radar") == "ok"]
    water = np.array([r["new_water"] for r in radar]) if radar else np.empty(0)
    sar_p = [r["sar_p"] for r in radar]
    share_water = float(np.mean(water >= 0.2)) if radar else float("nan")
    share_p = float(np.mean([p is not None and p <= 0.05 for p in sar_p])) if radar else float("nan")
    parts[year] = dict(n=len(radar), water=share_water, p=share_p)
    print(f"== {year}: {len(group)} plots; usable radar {len(radar)}; outages {sum(1 for r in group if 'outage' in r)}")
    print("   radar status:", dict(Counter((r.get('radar') or 'none')[:30] for r in group)))
    if radar:
        print("   pairs:", dict(Counter((r["sar_pre_date"], r["sar_post_date"], r["orbit"], r["direction"]) for r in radar)))
        print(f"   new_water p25,50,75,max {np.round(np.percentile(water, [25, 50, 75, 100]), 3).tolist()}; >=0.2: {share_water:.1%}; mean water pre {np.mean([r['water_pre'] for r in radar]):.3f} post {np.mean([r['water_post'] for r in radar]):.3f}")
        print(f"   SAR p<=0.05: {share_p:.1%}; p deciles {np.histogram([p for p in sar_p if p is not None], bins=np.linspace(0, 1, 11))[0].tolist()}; insufficient {sum(p is None for p in sar_p)}")
        print(f"   VH change p25,50,75 {np.round(np.percentile([r['vh_change'] for r in radar], [25, 50, 75]), 2).tolist()} dB; neighbour median {np.median([r['vh_neighbour'] for r in radar if r['vh_neighbour'] is not None]):.2f}")
        print(f"   radar field conditions (p<=.05 or new water>=.2): {np.mean([r['sar_field'] for r in radar]):.1%}")
        for site in sorted({r["site"] for r in radar}):
            s = [r for r in radar if r["site"] == site]
            print(f"     {site}: n={len(s)} median new water {np.median([r['new_water'] for r in s]):.3f}; >=0.2 {np.mean([r['new_water'] >= .2 for r in s]):.0%}; p<=.05 {np.mean([r['sar_p'] is not None and r['sar_p'] <= .05 for r in s]):.0%}; median VH {np.median([r['vh_change'] for r in s]):+.2f}")
    opt = [r for r in group if r.get("delta") is not None]
    print(f"   optical: pair found {sum(1 for r in group if r.get('optical_pre') and r.get('optical_post'))}; compared {len(opt)}; errors {sum(1 for r in group if 'optical_error' in r)}")
    if opt:
        print(f"   optical change median {np.median([r['delta'] for r in opt]):.3f}; strong field {sum(r['strong_field'] for r in opt)}; moderate field {sum(r['moderate_field'] for r in opt)}; post dates {dict(Counter((r['optical_post'] or '')[11:19] for r in opt))}")

a, b = parts[2025], parts[2024]
testable = a["n"] >= 30 and b["n"] >= 30
water_ok = a["water"] >= 3 * b["water"] and a["water"] - b["water"] >= 0.15
p_ok = a["p"] >= 2 * b["p"] and a["p"] - b["p"] >= 0.15
print(f"\nNew water >=0.2: 2025 {a['water']:.1%}, 2024 {b['water']:.1%}: {'passes' if water_ok else 'does not pass'}")
print(f"SAR p<=0.05: 2025 {a['p']:.1%}, 2024 {b['p']:.1%}: {'passes' if p_ok else 'does not pass'}")
print("RESULT:", "NOT TESTABLE" if not testable else "PASS" if water_ok and p_ok else "PARTIAL" if water_ok or p_ok else "MISS")

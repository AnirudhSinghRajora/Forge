"""Live smoke test: python -m app.tools.geo.smoke --lat 29.53 --lon 75.03 --start 2026-10-10 --end 2026-10-31"""
from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date, timedelta

from . import optical_compare, search_and_qa, search_sar
from .replay import flatten_numbers


def square(lat: float, lon: float, side_m: float = 120.0) -> dict:
    dlat = side_m / 2 / 111_320
    dlon = dlat / max(0.1, math.cos(math.radians(lat)))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]
    return {"type": "Polygon", "coordinates": [ring]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--side", type=float, default=120.0)
    ap.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=21))
    ap.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = ap.parse_args()
    polygon = square(args.lat, args.lon, args.side)

    t0 = time.time()
    results = search_and_qa(polygon, args.start, args.end)
    print(f"optical search + QA: {time.time() - t0:.1f} s")
    for scene, qa in results:
        print(" ", scene.date, scene.id, qa.status, qa.reasons, "valid", qa.plot_valid_frac, "ctx", qa.context_ndvi_median)
    accepted = [s for s, q in results if q.status == "accepted"]
    if len(accepted) >= 2:
        t0 = time.time()
        optical, neighbours = optical_compare(polygon, accepted[-2].id, accepted[-1].id, seed=7)
        print(f"optical_compare: {time.time() - t0:.1f} s")
        print(json.dumps(flatten_numbers(optical, neighbours), indent=1))
        print("twin:", neighbours.counterfactual.method if neighbours.counterfactual else None)
    print("radar:", [(s.date.isoformat(), s.orbit_state, s.relative_orbit) for s in search_sar(polygon, args.start, args.end)])


if __name__ == "__main__":
    main()

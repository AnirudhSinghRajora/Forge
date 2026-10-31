"""Run every engine function on one real plot, timing each. Real data; not a pytest.

PYTHONPATH=. uv run python tests/geo_full_case.py --name umrawat --lat 28.76654 --lon 76.18455 \\
    --event 2024-03-02 --start 2024-02-05 --end 2024-03-22 --s2-pre ID --s2-post ID --s1-pre ID --s1-post ID
Scene ids are optional: without them the engine picks by the contract's rule (latest accepted before
the event, earliest accepted after it). Output: backend/var/geo_validation/<name>/.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, timedelta

from app.evidence.schema import ReplayCore
from app.tools import geo
from app.tools.geo.base import var_dir
from tests.geo_fpr_sirsa import square


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--side", type=float, default=120.0)
    ap.add_argument("--event", type=date.fromisoformat, required=True)
    ap.add_argument("--start", type=date.fromisoformat)
    ap.add_argument("--end", type=date.fromisoformat)
    ap.add_argument("--s2-pre")
    ap.add_argument("--s2-post")
    ap.add_argument("--s1-pre")
    ap.add_argument("--s1-post")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--replay", action="store_true")
    args = ap.parse_args()

    out = var_dir() / "geo_validation" / args.name
    out.mkdir(parents=True, exist_ok=True)
    polygon = square(args.lon, args.lat, args.side)
    start = args.start or args.event - timedelta(days=25)
    end = args.end or args.event + timedelta(days=20)
    timings: dict[str, float] = {}
    result: dict = {"polygon": polygon, "plot": geo.plot_info(polygon).model_dump()}

    def step(name, fn):
        t0 = time.time()
        value = fn()
        timings[name] = round(time.time() - t0, 1)
        print(f"[{name}] {timings[name]} s", flush=True)
        return value

    scenes = step("search_and_qa", lambda: geo.search_and_qa(polygon, start, end))
    result["scenes"] = [
        {"id": s.id, "date": str(s.date), "cloud": s.cloud_pct, "status": q.status, "reasons": q.reasons,
         "plot_valid": q.plot_valid_frac, "ctx_ndvi": q.context_ndvi_median}
        for s, q in scenes
    ]
    for row in result["scenes"]:
        print(" ", row["date"], row["status"], "cloud", row["cloud"], "valid", row["plot_valid"], "ctx", row["ctx_ndvi"], row["reasons"], flush=True)

    usable = [(s, q) for s, q in scenes if q.status in ("accepted", "suspect")]
    pre_id = args.s2_pre or next((s.id for s, q in reversed(usable) if s.date <= args.event and q.status == "accepted"), None)
    post_id = args.s2_post or next((s.id for s, q in usable if s.date > args.event), None)
    print("optical pair:", pre_id, post_id, flush=True)

    optical = neighbours = sar = hist = village = fade = None
    if pre_id and post_id:
        optical, neighbours = step("optical_compare", lambda: geo.optical_compare(polygon, pre_id, post_id, args.seed))
        hist = step("history", lambda: geo.history(polygon, args.event, current_delta=optical.plot_delta_ndvi, current_pre_ndvi=optical.pre.ndvi_median))
    if args.s1_pre and args.s1_post:
        sar = step("sar_compare", lambda: geo.sar_compare(polygon, args.s1_pre, args.s1_post, args.seed))

    sensor = None
    if optical is not None:
        sensor, a, b = "s2", pre_id, post_id
    elif sar is not None and sar.usable:
        sensor, a, b = "s1", args.s1_pre, args.s1_post
    if sensor:
        village = step("village_witness", lambda: geo.village_witness(polygon, a, b, args.seed, sensor))
        fade = step("scale_fade", lambda: geo.scale_fade(polygon, a, b, out, sensor))
    tl = step("timeline", lambda: geo.timeline(polygon, start, end))
    chips = []
    if pre_id and post_id:
        chips = step("render_chips", lambda: geo.render_chips(polygon, pre_id, post_id, out, args.s1_pre, args.s1_post))

    numbers = geo.flatten_numbers(optical, neighbours, sar, hist, village, fade)
    for key, value in (("optical", optical), ("neighbours", neighbours), ("sar", sar), ("history", hist), ("village", village), ("scale_fade", fade)):
        result[key] = value.model_dump(mode="json") if value is not None else None
    result["timeline"] = [p.model_dump(mode="json") for p in tl]
    result["chips"] = [c.model_dump(mode="json") for c in chips]
    result["numbers"] = numbers
    result["timings_s"] = timings

    if args.replay:
        core = ReplayCore(
            engine_version=geo.ENGINE_VERSION, polygon=polygon, event_date=args.event, optical_pre_id=pre_id,
            optical_post_id=post_id, sar_pre_id=args.s1_pre, sar_post_id=args.s1_post,
            history_scene_ids=geo.history_scene_ids(hist) if hist else [], seed=args.seed, numbers=numbers,
        )
        again = step("replay", lambda: geo.replay(core))
        diffs = {k: (numbers.get(k), again.get(k)) for k in set(numbers) | set(again) if numbers.get(k) != again.get(k)}
        result["replay_identical"] = not diffs
        result["replay_diffs"] = {k: list(v) for k, v in diffs.items()}
        print("replay identical:", not diffs, "of", len(numbers), "numbers; diffs:", diffs, flush=True)
    (out / "result.json").write_text(json.dumps(result, indent=1, default=str))
    print("timings", timings, flush=True)
    print(json.dumps({k: v for k, v in numbers.items()}, indent=0), flush=True)


if __name__ == "__main__":
    main()

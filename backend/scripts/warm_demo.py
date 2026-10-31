#!/usr/bin/env python3
"""Warm a deployment after any deployment or engine change: real cases through the public API.

    cd backend && uv run python scripts/warm_demo.py --base-url https://your.host [--verify]

Every plot is a real input through the normal path, with no fixture data, and nothing is set that a
farmer could not enter. Each run creates new cases, so it is safe to repeat. Investigations and checks
run one at a time, because each one downloads satellite imagery.

The server limits investigations and checks per IP. A run of the default plots stays under those limits.
Past them (repeat runs, or --with-ratia with --verify) this pauses for as long as the server says and
carries on; --limit-wait sets how long it is willing to wait. For a larger warm-up, raise
RATE_INVESTIGATIONS_PER_HOUR and RATE_VERIFY_PER_HOUR on the server for its duration.

Sources are in docs/validation/events.md:
- `insured` is never sent. Bhiwani is a signal case, not a claim case (C1), and insurance is the
  farmer's answer for Godavari (A5) and Ratia.
- crop_stage is sent only where a source supports it. Bhiwani: standing wheat (C1). Godavari stage
  varies by plot (A6) and Ratia was part-way through harvest (B1), so both stay unknown.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass

import httpx

TERMINAL = ("done", "failed", "interrupted", "error")
VERIFY_RETRY_S = 5.0
DEFAULT_LIMIT_WAIT_S = 3700.0  # a limit's window is one hour


def square(lon: float, lat: float, side_m: float) -> dict:
    """The same arithmetic as tests/geo_fpr_sirsa.py:square, which built the validated plots. The seed
    hashes the polygon, so these floats go out unrounded."""
    dlat = side_m / 2 / 111_320
    dlon = dlat / math.cos(math.radians(lat))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat], [lon - dlon, lat - dlat]]
    return {"type": "Polygon", "coordinates": [ring]}


@dataclass(frozen=True)
class DemoPlot:
    name: str
    lat: float
    lon: float
    side_m: float
    event_date: str
    crop: str
    event_type: str
    text: str
    crop_stage: str | None = None
    optional: bool = False

    @property
    def polygon(self) -> dict:
        return square(self.lon, self.lat, self.side_m)


PLOTS = (
    DemoPlot("bhiwani-strongest", 28.700911, 76.215719, 113.1, "2024-03-03", "wheat", "hail",
             "Hail damaged the standing wheat, March 2024.", crop_stage="standing"),
    DemoPlot("bhiwani-typical", 28.715212, 76.231138, 104.7, "2024-03-03", "wheat", "hail",
             "Hail damaged the standing wheat, March 2024.", crop_stage="standing"),
    # Beside Anaparthi: the strongest of 51 usable plots scanned there (engine-results.md section 4), so
    # its selection note says so. Its crop was days from harvest and the plot also fell in other years.
    DemoPlot("godavari-arnab", 16.906738, 81.975164, 112.3, "2026-10-28", "paddy", "cyclone",
             "Cyclone Arnab damaged the paddy, October 2026."),
    # Jallopur's cropland point, a named village in Ratia tehsil (events.md B2).
    DemoPlot("ratia-hail", 29.69151, 75.49735, 100.0, "2026-10-24", "paddy", "hail",
             "Hail damaged the paddy on the evening of 24 October 2026.", optional=True),
)


def choose(with_ratia: bool, only: list[str] | None) -> list[DemoPlot]:
    if only:
        known = {p.name: p for p in PLOTS}
        return [known[name] for name in only]
    return [p for p in PLOTS if with_ratia or not p.optional]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Create real demo cases through the public API and investigate them.")
    ap.add_argument("--base-url", required=True, help="the deployment, for example https://your.host")
    ap.add_argument("--verify", action="store_true", help="also run the full check for each sealed case, and wait")
    ap.add_argument("--with-ratia", action="store_true", help="add the optional Ratia tehsil case")
    ap.add_argument("--only", nargs="+", choices=[p.name for p in PLOTS], help="run just these plots")
    ap.add_argument("--lang", choices=("hi", "en", "te"), default="hi", help="the case's language")
    ap.add_argument("--timeout", type=float, default=900.0, help="seconds to wait for each case to seal")
    ap.add_argument("--verify-timeout", type=float, default=1800.0, help="seconds to wait for each full check")
    ap.add_argument("--poll", type=float, default=5.0, help="seconds between looks at a running case")
    ap.add_argument("--limit-wait", type=float, default=DEFAULT_LIMIT_WAIT_S,
                    help="seconds to pause when the server's rate limit says to wait; 0 fails at once")
    ap.add_argument("--dry-run", action="store_true", help="print what would be sent, and send nothing")
    args = ap.parse_args(argv)
    if not args.base_url.startswith(("http://", "https://")):
        ap.error("--base-url must start with http:// or https://")
    args.base_url = args.base_url.rstrip("/")
    if args.timeout <= 0 or args.verify_timeout <= 0 or args.poll <= 0:
        ap.error("--timeout, --verify-timeout and --poll must be positive")
    return args


def _ok(response: httpx.Response, what: str) -> dict:
    if response.status_code >= 400:
        raise RuntimeError(f"{what}: HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


def _pause_for(response: httpx.Response, what: str, limit_wait: float) -> None:
    """Sits out a 429 for as long as the server says, or raises if that is more than we may wait."""
    wait = float(response.headers.get("retry-after") or VERIFY_RETRY_S)
    if wait > limit_wait:
        raise RuntimeError(f"{what}: rate limited for another {wait:.0f} s; see --limit-wait")
    print(f"{what}: the server's rate limit says wait {wait:.0f} s; pausing", flush=True)
    time.sleep(wait + 1)


def _sent(send, what: str, limit_wait: float) -> httpx.Response:
    while True:
        response = send()
        if response.status_code != 429:
            return response
        _pause_for(response, what, limit_wait)


def case_payloads(plot: DemoPlot, lang: str) -> tuple[dict, dict, dict]:
    """(form for POST /api/cases, body for PUT .../plot, body for PATCH). `insured` is never in these."""
    form = {"lat": str(plot.lat), "lon": str(plot.lon), "lang": lang, "text": plot.text}
    patch = {"crop": plot.crop, "event_type": plot.event_type, "event_date": plot.event_date}
    if plot.crop_stage:
        patch["crop_stage"] = plot.crop_stage
    return form, {"polygon": plot.polygon}, patch


def create_case(client: httpx.Client, plot: DemoPlot, lang: str, limit_wait: float = DEFAULT_LIMIT_WAIT_S) -> str:
    form, body, patch = case_payloads(plot, lang)
    created = _sent(lambda: client.post("/api/cases", data=form), "create case", limit_wait)
    case_id = _ok(created, "create case")["case_id"]
    _ok(client.put(f"/api/cases/{case_id}/plot", json=body), "set plot")
    stored = _ok(client.patch(f"/api/cases/{case_id}", json=patch), "set details")
    if stored["plot"]["geometry"] != body["polygon"]:
        raise RuntimeError("the server stored a different polygon, so the seed would not match the validated run")
    return case_id


def wait_for_seal(client: httpx.Client, case_id: str, started: float, timeout: float, poll: float) -> dict:
    """Polls the case until it seals or its run ends, and notes when the verdict first appeared.
    A dropped request is not a failure, because the run carries on with no client attached."""
    out: dict = {"envelope": None, "verdict_s": None, "sealed_s": None, "timed_out": False}
    ended_looks = 0
    while True:
        elapsed = time.monotonic() - started
        try:
            response = client.get(f"/api/cases/{case_id}")
            envelope = response.json() if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            envelope = None
        if envelope is not None:
            out["envelope"] = envelope
            if envelope.get("verdict_ready") and out["verdict_s"] is None:
                out["verdict_s"] = round(elapsed, 1)
            if envelope.get("sealed"):
                out["sealed_s"] = round(elapsed, 1)
                return out
            run = envelope["case"].get("latest_run") or {}
            pending = any(e.get("status") == "pending" for e in (envelope.get("exhibits") or {}).values())
            # One read can catch the evidence just before the seal and the run just after it finished,
            # so the run has only ended unsealed if the next look says the same.
            if run.get("status") in TERMINAL and not envelope["case"].get("active_run_id") and not pending:
                ended_looks += 1
                if ended_looks >= 2:
                    return out
            else:
                ended_looks = 0
        if elapsed > timeout:
            out["timed_out"] = True
            return out
        time.sleep(poll)


def sse_data(lines) -> list[dict]:
    """The JSON payloads in some SSE lines, skipping pings and anything that is not JSON."""
    out = []
    for line in lines:
        if line.startswith("data:"):
            try:
                out.append(json.loads(line[5:].strip()))
            except ValueError:
                continue
    return out


def run_verify(client: httpx.Client, evidence_hash: str, timeout: float, limit_wait: float = DEFAULT_LIMIT_WAIT_S) -> dict:
    """Follows the check to its result. The job runs on the server, so a dropped stream resumes
    from the last event seen and never starts a second download."""
    started = time.monotonic()
    after, last_error = 0, None
    while time.monotonic() - started < timeout:
        try:
            url = f"/api/verify/{evidence_hash}" + (f"?after={after}" if after else "")
            with client.stream("GET", url) as response:
                if response.status_code == 429:
                    _pause_for(response, "full check", min(limit_wait, timeout - (time.monotonic() - started)))
                    continue
                if response.status_code >= 400:
                    raise RuntimeError(f"verify: HTTP {response.status_code}")
                for line in response.iter_lines():
                    for event in sse_data([line]):
                        after = event.get("seq", after)
                        if event.get("type") == "result":
                            return {**event, "verify_s": round(time.monotonic() - started, 1)}
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if time.monotonic() - started < timeout:
            time.sleep(VERIFY_RETRY_S)
    return {"status": "timed_out", "error": last_error, "verify_s": round(time.monotonic() - started, 1)}


def warm_one(client: httpx.Client, plot: DemoPlot, base_url: str, *, verify: bool, lang: str, timeout: float,
             verify_timeout: float, poll: float, limit_wait: float = DEFAULT_LIMIT_WAIT_S) -> dict:
    row: dict = {"name": plot.name, "case_id": None, "level": None, "hash": None, "url": None, "error": None,
                 "verdict_s": None, "sealed_s": None, "verify_status": None, "verify_s": None}
    started = time.monotonic()
    try:
        case_id = create_case(client, plot, lang, limit_wait)
        row["case_id"], row["url"] = case_id, f"{base_url}/case/{case_id}"
        print(f"[{plot.name}] case {case_id}: investigating", flush=True)
        started_run = _sent(lambda: client.post(f"/api/cases/{case_id}/investigate"), "start investigation", limit_wait)
        _ok(started_run, "start investigation")
        waited = wait_for_seal(client, case_id, started, timeout, poll)
        row["verdict_s"], row["sealed_s"] = waited["verdict_s"], waited["sealed_s"]
        evidence = (waited["envelope"] or {}).get("evidence") or {}
        row["level"] = (evidence.get("verdict") or {}).get("level")
        row["hash"] = evidence.get("evidence_hash")
        if not row["hash"]:
            row["error"] = "timed out before sealing" if waited["timed_out"] else "the run ended without a seal"
        elif verify:
            print(f"[{plot.name}] sealed; running the full check", flush=True)
            result = run_verify(client, row["hash"], verify_timeout, limit_wait)
            row["verify_status"], row["verify_s"] = result.get("status"), result.get("verify_s")
    except (RuntimeError, httpx.HTTPError, KeyError, ValueError) as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def report(row: dict) -> None:
    print(f"\n{row['name']}\n  case     {row['case_id']}\n  verdict  {row['level']}\n  hash     {row['hash']}\n  url      {row['url']}")
    print(f"  timings  verdict {row['verdict_s']} s, sealed {row['sealed_s']} s"
          + (f", check {row['verify_s']} s: {row['verify_status']}" if row["verify_status"] else ""))
    if row["error"]:
        print(f"  FAILED   {row['error']}")


def succeeded(row: dict, verify: bool) -> bool:
    if row["error"] or not row["hash"]:
        return False
    return not verify or row["verify_status"] == "verified"


def run(args: argparse.Namespace, client: httpx.Client) -> int:
    rows = []
    for plot in choose(args.with_ratia, args.only):
        row = warm_one(client, plot, args.base_url, verify=args.verify, lang=args.lang, timeout=args.timeout,
                       verify_timeout=args.verify_timeout, poll=args.poll, limit_wait=args.limit_wait)
        report(row)
        rows.append(row)
    good = sum(succeeded(r, args.verify) for r in rows)
    print(f"\n{good} of {len(rows)} cases finished" + (" sealed and verified" if args.verify else " sealed"))
    return 0 if good == len(rows) else 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.dry_run:
        for plot in choose(args.with_ratia, args.only):
            form, body, patch = case_payloads(plot, args.lang)
            print(json.dumps({"name": plot.name, "form": form, "plot": body, "patch": patch}, indent=2))
        return 0
    timeout = httpx.Timeout(60.0, read=120.0)
    with httpx.Client(base_url=args.base_url, timeout=timeout, follow_redirects=True) as client:
        return run(args, client)


if __name__ == "__main__":
    sys.exit(main())

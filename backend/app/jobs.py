"""Background jobs: SACHET archive, re-checks when a new accepted scene exists, deadline upkeep.

Reachable through POST /api/jobs/tick and through an in-process APScheduler. Each job reports what
it did and failures stay in their own job.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.agent import claim_path, runner
from app.agent.parse import today_ist
from app.config import get_settings
from app.db import Action, Case, EvidenceRow, Plot, session_scope

log = logging.getLogger(__name__)
MAX_RECHECKS_PER_TICK = 5


def archive_alerts_safe() -> dict:
    from app.tools import alerts

    try:
        report = alerts.archive()
        log.info("SACHET archive: %s", report)
        return report
    except Exception as exc:  # an unreachable feed must not stop anything else  # noqa: BLE001
        log.warning("SACHET archive failed: %s", exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def _open_rechecks() -> list[dict]:
    """Cases with an open re-check action that are due and have no run active."""
    now = datetime.now(UTC)
    out = []
    with session_scope() as s:
        rows = s.scalars(select(Action).where(Action.type == "recheck", Action.status == "open")).all()
        for action in rows:
            if action.due_at is not None and action.due_at > now:
                continue
            plot = s.scalar(select(Plot).where(Plot.case_id == action.case_id))
            case = s.get(Case, action.case_id)
            evidence = s.scalars(
                select(EvidenceRow).where(EvidenceRow.case_id == action.case_id)
                .order_by(EvidenceRow.created_at.desc())
            ).first()
            if plot is None or case is None or evidence is None or case.event_date is None:
                continue
            considered = (evidence.json.get("optical") or {}).get("scenes_considered") or []
            out.append({
                "case_id": case.id, "polygon": plot.geometry, "event_date": case.event_date,
                "known": {s_["id"] for s_ in considered},
                "retry_now": action.payload.get("basis") == "archive-retry",
            })
    return out


def recheck_open_cases() -> dict:
    """A new run with trigger=scheduler only if a new scene passes QA after the event."""
    from app.tools import geo

    started, checked, errors = [], 0, []
    today = today_ist()
    for item in _open_rechecks()[:MAX_RECHECKS_PER_TICK]:
        if runner.active_run_id(item["case_id"]):
            continue
        checked += 1
        if item["retry_now"]:
            # The scene was fine and only the archive was slow, so this needs no new pass.
            run_id, _ = runner.start_run(item["case_id"], "scheduler")
            started.append({"case_id": item["case_id"], "run_id": run_id, "scene": None})
            continue
        try:
            start = item["event_date"] + timedelta(days=1)
            scenes = geo.search_optical(item["polygon"], start, today) if start <= today else []
            for scene in sorted(scenes, key=lambda x: x.datetime):
                if scene.id in item["known"]:
                    continue
                if geo.qa_scene(scene, item["polygon"]).status == "accepted":
                    run_id, _ = runner.start_run(item["case_id"], "scheduler")
                    started.append({"case_id": item["case_id"], "run_id": run_id, "scene": scene.id})
                    break
        except Exception as exc:  # a satellite outage only postpones the re-check to the next tick  # noqa: BLE001
            log.warning("re-check failed for %s: %s", item["case_id"], exc)
            errors.append({"case_id": item["case_id"], "error": f"{type(exc).__name__}: {exc}"})
    return {"checked": checked, "started": started, "errors": errors}


def update_deadlines() -> dict:
    """Keeps case status in step with the route and the clock."""
    changed = 0
    with session_scope() as s:
        cases = s.scalars(select(Case).where(Case.status.in_(("open", "intimation_due")))).all()
        for case in cases:
            path, _ = claim_path.for_case(case, "en")
            status = "intimation_due" if path.countdown_applies else "open"
            if case.status != status:
                case.status = status
                changed += 1
    return {"cases_changed": changed}


def tick() -> dict:
    report = {"at": datetime.now(UTC).isoformat(), "alerts": archive_alerts_safe()}
    for name, job in (("rechecks", recheck_open_cases), ("deadlines", update_deadlines)):
        try:
            report[name] = job()
        except Exception as exc:
            log.exception("job %s failed", name)
            report[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return report


def start_scheduler() -> Callable[[], None]:
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(daemon=True, timezone="UTC")
    scheduler.add_job(tick, "interval", minutes=get_settings().scheduler_interval_min, id="tick",
                      max_instances=1, coalesce=True)
    scheduler.start()
    return lambda: scheduler.shutdown(wait=False)

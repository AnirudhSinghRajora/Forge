"""Background jobs: SACHET archive, re-checks when a new accepted scene exists, deadline upkeep.

Reachable through POST /api/jobs/tick and through an in-process APScheduler. Each job reports what
it did and failures stay in their own job.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app import errors
from app.agent import claim_path, rubric, runner
from app.agent.parse import today_ist
from app.config import get_settings
from app.db import Action, Case, EvidenceRow, Plot, session_scope

log = logging.getLogger(__name__)
MAX_RECHECKS_PER_TICK = 5
NO_SCENE_WAIT = timedelta(hours=12)  # a Sentinel-2 pass comes about every five days
OUTAGE_WAIT = timedelta(hours=1)
RUN_RETRY_WAIT = timedelta(hours=1)  # only felt if the run dies before it decides a new re-check


def archive_alerts_safe() -> dict:
    from app.tools import alerts

    try:
        report = alerts.archive()
        log.info("SACHET archive: %s", report)
        return report
    except Exception as exc:  # an unreachable feed must not stop anything else  # noqa: BLE001
        log.warning("SACHET archive failed: %s", exc)
        return {"error": type(exc).__name__}


def _open_rechecks() -> list[dict]:
    """Open re-checks that are due, oldest first, with no run active. Anything past its window is
    closed here, since no new image could change it. Filtering comes first, so that a case that keeps
    coming round cannot use up a tick's slots and starve the others."""
    now = datetime.now(UTC)
    today = today_ist()
    out = []
    with session_scope() as s:
        rows = s.scalars(
            select(Action).where(Action.type == "recheck", Action.status == "open").order_by(Action.due_at)
        ).all()
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
            retry_now = action.payload.get("basis") == "archive-retry"
            event_text = (evidence.json.get("event") or {}).get("date")
            event_date = date.fromisoformat(event_text) if event_text else case.event_date
            window_end = event_date + timedelta(days=rubric.RECHECK_WINDOW_DAYS)
            if not retry_now and today > window_end:
                action.status = "closed"
                action.payload = {**action.payload, "closed_reason": "post_event_window_passed"}
                if case.status == "rechecking":
                    case.status = "open"
                continue
            if runner.active_run_id(action.case_id):
                continue
            considered = (evidence.json.get("optical") or {}).get("scenes_considered") or []
            out.append({
                "action_id": action.id, "case_id": case.id, "polygon": plot.geometry,
                "event_date": event_date, "window_end": window_end,
                "known": {s_["id"] for s_ in considered}, "retry_now": retry_now,
            })
    return out


def _postpone(action_id: str, wait: timedelta) -> None:
    """Sends this one to the back of the queue. A run that starts replaces it with its own decision."""
    with session_scope() as s:
        action = s.get(Action, action_id)
        if action is not None and action.status == "open":
            action.due_at = datetime.now(UTC) + wait


def recheck_open_cases() -> dict:
    """A new run with trigger=scheduler only if a new scene passes QA after the event."""
    from app.tools import geo

    started, checked, errors_seen = [], 0, []
    today = today_ist()
    for item in _open_rechecks()[:MAX_RECHECKS_PER_TICK]:
        checked += 1
        try:
            if item["retry_now"]:
                # The scene was fine and only the archive was slow, so this needs no new pass.
                _postpone(item["action_id"], RUN_RETRY_WAIT)
                run_id, _ = runner.start_run(item["case_id"], "scheduler")
                started.append({"case_id": item["case_id"], "run_id": run_id, "scene": None})
                continue
            start = item["event_date"] + timedelta(days=1)
            end = min(item["window_end"], today)
            scenes = geo.search_optical(item["polygon"], start, end) if start <= end else []
            for scene in sorted(scenes, key=lambda x: x.datetime):
                if scene.id in item["known"]:
                    continue
                if geo.qa_scene(scene, item["polygon"]).status == "accepted":
                    _postpone(item["action_id"], RUN_RETRY_WAIT)
                    run_id, _ = runner.start_run(item["case_id"], "scheduler")
                    started.append({"case_id": item["case_id"], "run_id": run_id, "scene": scene.id})
                    break
            else:
                _postpone(item["action_id"], NO_SCENE_WAIT)
        except runner.QueueFull:
            log.info("the run queue is full; the remaining re-checks wait for the next tick")
            break
        except Exception as exc:  # a satellite outage only postpones the re-check  # noqa: BLE001
            log.warning("re-check failed for %s: %s", item["case_id"], errors.scrub(exc))
            _postpone(item["action_id"], OUTAGE_WAIT)
            errors_seen.append({"case_id": item["case_id"], "error": type(exc).__name__})
    return {"checked": checked, "started": started, "errors": errors_seen}


def update_deadlines() -> dict:
    """Keeps case status in step with the route and the clock. A case it cannot read does not stop
    the others, and each one commits on its own."""
    changed, failed = 0, []
    with session_scope() as s:
        ids = s.scalars(select(Case.id).where(Case.status.in_(("open", "intimation_due")))).all()
    for case_id in ids:
        try:
            with session_scope() as s:
                case = s.get(Case, case_id)
                path, _ = claim_path.for_case(case, "en")
                status = "intimation_due" if path.countdown_applies else "open"
                if case.status != status:
                    case.status = status
                    changed += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("could not update deadlines for %s: %s", case_id, errors.scrub(exc))
            failed.append(case_id)
    return {"cases_changed": changed, "cases_failed": failed}


def tick() -> dict:
    report = {"at": datetime.now(UTC).isoformat(), "alerts": archive_alerts_safe()}
    for name, job in (("rechecks", recheck_open_cases), ("deadlines", update_deadlines)):
        try:
            report[name] = job()
        except Exception as exc:
            log.exception("job %s failed", name)
            report[name] = {"error": type(exc).__name__}
    return report


def start_scheduler() -> Callable[[], None]:
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(daemon=True, timezone="UTC")
    scheduler.add_job(tick, "interval", minutes=get_settings().scheduler_interval_min, id="tick",
                      max_instances=1, coalesce=True)
    scheduler.start()
    return lambda: scheduler.shutdown(wait=False)

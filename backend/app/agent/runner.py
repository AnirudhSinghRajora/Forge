"""Run lifecycle: one active run per case, background threads, and a run that always terminates.

Runs execute in a thread pool because the geo engine is synchronous. Nothing here depends on an SSE
client being connected, so a client disconnect or refresh cannot affect a run.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.agent.trace import Tracer
from app.config import get_settings
from app.db import Case, EvidenceRow, Run, RunEvent, new_id, session_scope, utcnow

log = logging.getLogger(__name__)

ACTIVE = ("queued", "running")
_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None


def _pool() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=get_settings().run_workers, thread_name_prefix="run"
        )
    return _executor


def active_run_id(case_id: str) -> str | None:
    with session_scope() as s:
        return s.scalar(
            select(Run.id)
            .where(Run.case_id == case_id, Run.status.in_(ACTIVE))
            .order_by(Run.started_at.desc())
            .limit(1)
        )


def start_run(case_id: str, trigger: str = "user") -> tuple[str, bool]:
    """Returns (run_id, created). Idempotent while a run is active, including concurrent callers."""
    with _lock:
        existing = active_run_id(case_id)
        if existing:
            return existing, False
        run_id = new_id()
        with session_scope() as s:
            s.add(Run(id=run_id, case_id=case_id, trigger=trigger, status="queued"))
    _pool().submit(_execute, run_id, case_id)
    return run_id, True


def start_retry(case_id: str, name: str) -> str | None:
    """A retry is a small run of its own. None if another run is active on this case."""
    with _lock:
        if active_run_id(case_id):
            return None
        run_id = new_id()
        with session_scope() as s:
            s.add(Run(id=run_id, case_id=case_id, trigger="retry", status="queued"))
    _pool().submit(_execute_retry, run_id, case_id, name)
    return run_id


def _execute_retry(run_id: str, case_id: str, name: str) -> None:
    tracer = Tracer(run_id)
    try:
        with session_scope() as s:
            s.get(Run, run_id).status = "running"
        from app.agent.graph import retry_exhibit

        finish_run(run_id, retry_exhibit(run_id, case_id, name, tracer))
    except Exception as exc:
        log.exception("retry %s failed", run_id)
        tracer.emit("error", "exhibits", "दोबारा कोशिश नहीं हो सकी", f"The retry failed: {exc}",
                    error=f"{type(exc).__name__}: {exc}")
        tracer.emit("done", "exhibits", "समाप्त", "Finished", status="failed", exhibit=name)
        finish_run(run_id, "failed", f"{type(exc).__name__}: {exc}")


def _next_seq(run_id: str) -> int:
    with session_scope() as s:
        seqs = s.scalars(select(RunEvent.seq).where(RunEvent.run_id == run_id)).all()
    return max(seqs, default=0)


def finish_run(run_id: str, status: str, error: str | None = None) -> None:
    with session_scope() as s:
        run = s.get(Run, run_id)
        if run is not None:
            run.status = status
            run.finished_at = utcnow()
            run.error = error


def _execute(run_id: str, case_id: str) -> None:
    tracer = Tracer(run_id)
    try:
        with session_scope() as s:
            s.get(Run, run_id).status = "running"
        from app.agent.graph import run_investigation

        status = run_investigation(run_id, case_id, tracer)
        finish_run(run_id, status)
    except Exception as exc:  # the last line of defence: a run must always reach a terminal state
        log.exception("run %s failed", run_id)
        tracer.emit(
            "error", "runner",
            "जाँच बीच में रुक गई। अब तक जो सबूत मिले वे सुरक्षित हैं।",
            "The investigation stopped unexpectedly. Evidence gathered so far is kept.",
            error=f"{type(exc).__name__}: {exc}",
        )
        tracer.emit("done", "runner", "जाँच समाप्त", "Investigation ended", status="failed")
        finish_run(run_id, "failed", f"{type(exc).__name__}: {exc}")


def recover_interrupted() -> int:
    """A restart kills in-flight threads. Close those runs so that no SSE client waits forever."""
    with session_scope() as s:
        stuck = s.scalars(select(Run).where(Run.status.in_(ACTIVE))).all()
        ids = [r.id for r in stuck]
    for run_id in ids:
        tracer = Tracer(run_id, _next_seq(run_id))
        tracer.emit(
            "error", "runner",
            "सर्वर दोबारा शुरू हुआ, इसलिए यह जाँच अधूरी रह गई। कृपया फिर से जाँच शुरू करें।",
            "The server restarted, so this investigation did not finish. Please start it again.",
        )
        tracer.emit("done", "runner", "जाँच समाप्त", "Investigation ended", status="interrupted")
        finish_run(run_id, "interrupted", "server restarted during the run")
        with session_scope() as s:
            row = s.scalar(select(EvidenceRow).where(EvidenceRow.run_id == run_id))
            if row is not None and row.exhibits:
                row.exhibits = {
                    name: {**entry, "status": "failed", "reason": "the server restarted"}
                    if entry.get("status") == "pending" else entry
                    for name, entry in row.exhibits.items()
                }
    return len(ids)


def set_case_status(case_id: str, status: str) -> None:
    with session_scope() as s:
        case = s.get(Case, case_id)
        if case is not None:
            case.status = status

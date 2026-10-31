"""Trace events: persisted to run_events first, so a client can always replay from any seq."""
from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, date, datetime

from app.db import RunEvent, session_scope
from app.evidence.schema import TraceEvent

log = logging.getLogger(__name__)


def _jsonable(value):
    if isinstance(value, datetime | date):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return str(value)


class Tracer:
    """Thread-safe (nodes run some tools in parallel). A persistence failure must not kill a run."""

    def __init__(self, run_id: str, start_seq: int = 0):
        self.run_id = run_id
        self._seq = start_seq
        self._lock = threading.Lock()

    def emit(self, type_: str, node: str, title_hi: str, title_en: str, **detail) -> TraceEvent:
        with self._lock:
            self._seq += 1
            event = TraceEvent(
                seq=self._seq,
                run_id=self.run_id,
                ts=datetime.now(UTC),
                type=type_,
                node=node,
                title_hi=title_hi,
                title_en=title_en,
                detail=json.loads(json.dumps(detail, default=_jsonable)),
            )
            try:
                with session_scope() as s:
                    s.add(
                        RunEvent(
                            run_id=self.run_id,
                            seq=event.seq,
                            type=event.type,
                            payload=event.model_dump(mode="json"),
                            ts=event.ts,
                        )
                    )
            except Exception:
                log.exception("could not persist trace event %s for run %s", event.seq, self.run_id)
            return event

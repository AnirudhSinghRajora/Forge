"""SQLAlchemy models (02 §6, without PostGIS: geometry is GeoJSON in a JSON column)."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class UtcDateTime(TypeDecorator):
    """Always aware UTC in Python. SQLite would otherwise drop the offset without converting it."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(32))
    lang: Mapped[str] = mapped_column(String(8), default="hi")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    lang: Mapped[str] = mapped_column(String(8), default="hi")
    transcript: Mapped[str | None] = mapped_column(Text)
    crop: Mapped[str | None] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(32), default="unknown")
    event_date: Mapped[date | None] = mapped_column(Date)
    event_time: Mapped[str | None] = mapped_column(String(8))  # HH:MM IST, as the farmer gave it
    insured: Mapped[str | None] = mapped_column(String(8))  # yes | no | unknown
    crop_stage: Mapped[str | None] = mapped_column(String(20))
    date_source: Mapped[str] = mapped_column(String(32), default="farmer")
    proposed_event_date: Mapped[date | None] = mapped_column(Date)
    parsed: Mapped[dict] = mapped_column(JSON, default=dict)
    needs: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="open")
    district: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, onupdate=utcnow
    )


class Plot(Base):
    __tablename__ = "plots"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), unique=True)
    geometry: Mapped[dict] = mapped_column(JSON)
    area_ha: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    centroid_lat: Mapped[float] = mapped_column(Float)
    crs: Mapped[str] = mapped_column(String(32))
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(16), default="drawn")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    trigger: Mapped[str] = mapped_column(String(16), default="user")
    # queued | running | done | failed | interrupted | needs_input
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    started_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    error: Mapped[str | None] = mapped_column(Text)


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)  # the TraceEvent as JSON
    ts: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class EvidenceRow(Base):
    __tablename__ = "evidence"
    __table_args__ = (Index("ix_evidence_hash", "evidence_hash"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    json: Mapped[dict] = mapped_column(JSON)
    verdict_level: Mapped[str | None] = mapped_column(String(32))
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    replay_core: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, onupdate=utcnow
    )


class Action(Base):
    __tablename__ = "actions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    # intimation_draft | submission | reminder | recheck
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="open")
    due_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class SceneCache(Base):
    __tablename__ = "scene_cache"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)  # scene + plot + previous scene
    scene_id: Mapped[str] = mapped_column(String(128), index=True)
    qa: Mapped[dict] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class AlertArchive(Base):
    __tablename__ = "alerts_archive"
    identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    sent: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)
    effective: Mapped[datetime | None] = mapped_column(UtcDateTime)
    expires: Mapped[datetime | None] = mapped_column(UtcDateTime)
    sender: Mapped[str | None] = mapped_column(String(200))
    event: Mapped[str | None] = mapped_column(String(200))
    severity: Mapped[str | None] = mapped_column(String(32))
    area_desc: Mapped[str | None] = mapped_column(Text)
    headline: Mapped[str | None] = mapped_column(Text)
    geocode: Mapped[dict | None] = mapped_column(JSON)
    url: Mapped[str | None] = mapped_column(Text)
    raw_xml: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


class PolicyEmbedding(Base):
    __tablename__ = "policy_embeddings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)  # model + clause id + text hash
    vector: Mapped[list] = mapped_column(JSON)


class ApiCache(Base):
    """Cached real API responses. The provenance (source, url, fetched_at) stays with the payload."""

    __tablename__ = "api_cache"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    source: Mapped[str] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | list] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if ":memory:" in url or url == "sqlite://":
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=10)


def init_db(url: str | None = None) -> Engine:
    """Create the engine and tables. Safe to call repeatedly; a new url replaces the old engine."""
    global _engine, _session_factory
    target = url or get_settings().db_url
    if _engine is None or str(_engine.url) != target:
        if _engine is not None:
            _engine.dispose()
        _engine = _build_engine(target)
        _session_factory = sessionmaker(_engine, expire_on_commit=False)
    Base.metadata.create_all(_engine)
    _add_missing_columns(_engine)
    return _engine


def _add_missing_columns(engine: Engine) -> None:
    """create_all never alters a table. New nullable columns are added so a dev DB keeps working."""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable:
                    kind = column.type.compile(engine.dialect)
                    conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {kind}'))


@contextmanager
def session_scope() -> Iterator[Session]:
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def cache_get(key: str) -> ApiCache | None:
    with session_scope() as s:
        return s.get(ApiCache, key)


def cache_put(key: str, source: str, url: str | None, payload: dict | list) -> None:
    with session_scope() as s:
        s.merge(ApiCache(key=key, source=source, url=url, payload=payload, fetched_at=utcnow()))

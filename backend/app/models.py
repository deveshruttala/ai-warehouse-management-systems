"""ORM models. Events are stored append-only; metrics are derived on read.

In production the ``events`` table maps naturally to a TimescaleDB hypertable
partitioned on ``ts`` for efficient time-range queries and retention policies.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(48), index=True)
    camera_id: Mapped[str] = mapped_column(String(48), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    zone: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[str] = mapped_column(Text)  # JSON-serialised payload

    __table_args__ = (
        Index("ix_events_type_ts", "event_type", "ts"),
        Index("ix_events_zone_ts", "zone", "ts"),
    )


class AnomalyRecordModel(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    camera_id: Mapped[str] = mapped_column(String(48), index=True)
    anomaly_type: Mapped[str] = mapped_column(String(48), index=True)
    zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[float] = mapped_column(Float)
    metric: Mapped[str] = mapped_column(String(64))
    observed: Mapped[float] = mapped_column(Float)
    expected: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

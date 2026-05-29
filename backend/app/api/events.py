"""Event log query endpoints."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_session
from ..models import EventRecord

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(
    limit: int = Query(100, ge=1, le=1000),
    event_type: str | None = Query(None),
    zone: str | None = Query(None),
    since: datetime | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = select(EventRecord).order_by(EventRecord.id.desc()).limit(limit)
    if event_type:
        stmt = stmt.where(EventRecord.event_type == event_type)
    if zone:
        stmt = stmt.where(EventRecord.zone == zone)
    if since:
        stmt = stmt.where(EventRecord.ts >= since)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "event_id": r.event_id,
            "event_type": r.event_type,
            "camera_id": r.camera_id,
            "ts": r.ts.isoformat(),
            "zone": r.zone,
            "track_id": r.track_id,
            "payload": json.loads(r.payload),
        }
        for r in rows
    ]


@router.get("/stats")
async def event_stats(session: AsyncSession = Depends(get_session)) -> dict:
    stmt = select(EventRecord.event_type, func.count()).group_by(EventRecord.event_type)
    rows = (await session.execute(stmt)).all()
    total = sum(c for _, c in rows)
    return {"total": total, "by_type": {t: c for t, c in rows}}

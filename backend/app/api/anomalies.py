"""Anomaly query & acknowledgement endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..analytics import get_engine
from ..database import get_session
from ..models import AnomalyRecordModel

router = APIRouter(prefix="/api/anomalies", tags=["anomalies"])


@router.get("")
async def list_anomalies(
    limit: int = Query(100, ge=1, le=1000),
    acknowledged: bool | None = Query(None),
    anomaly_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = select(AnomalyRecordModel).order_by(AnomalyRecordModel.id.desc()).limit(limit)
    if acknowledged is not None:
        stmt = stmt.where(AnomalyRecordModel.acknowledged == acknowledged)
    if anomaly_type:
        stmt = stmt.where(AnomalyRecordModel.anomaly_type == anomaly_type)
    rows = (await session.execute(stmt)).scalars().all()
    return [_serialize(r) for r in rows]


@router.post("/{anomaly_id}/ack")
async def acknowledge(anomaly_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(AnomalyRecordModel, anomaly_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    if not row.acknowledged:
        row.acknowledged = True
        await session.commit()
        engine = get_engine()
        engine.open_anomalies = max(0, engine.open_anomalies - 1)
    return _serialize(row)


def _serialize(r: AnomalyRecordModel) -> dict:
    return {
        "id": r.id,
        "ts": r.ts.isoformat(),
        "camera_id": r.camera_id,
        "anomaly_type": r.anomaly_type,
        "zone": r.zone,
        "severity": r.severity,
        "metric": r.metric,
        "observed": r.observed,
        "expected": r.expected,
        "message": r.message,
        "acknowledged": r.acknowledged,
    }

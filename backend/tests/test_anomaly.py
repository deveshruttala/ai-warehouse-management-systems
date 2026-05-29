"""Anomaly detector tests."""
from datetime import datetime, timedelta, timezone

from app.analytics import AnalyticsEngine
from app.anomaly import AnomalyDetector, RollingStat
from app.config import settings
from app.schemas import AnomalyType, Event, ZoneEnteredPayload


def test_rolling_stat_zscore():
    s = RollingStat(window=10)
    for _ in range(10):
        s.push(5.0)
    assert s.mean == 5.0
    assert s.std == 0.0
    # With zero variance, z-score is defined as 0.
    assert s.zscore(50) == 0.0
    s2 = RollingStat(window=10)
    for v in [1, 2, 3, 4, 5]:
        s2.push(v)
    assert s2.zscore(100) > 3


def test_zone_intrusion_is_instant():
    det = AnomalyDetector()
    ev = Event.of("c", ZoneEnteredPayload(track_id=1, zone="stockroom"))
    out = det.on_event(ev)
    assert len(out) == 1
    assert out[0].anomaly_type == AnomalyType.ZONE_INTRUSION
    assert out[0].zone == "stockroom"


def test_long_queue_threshold():
    det = AnomalyDetector()
    eng = AnalyticsEngine()
    now = datetime.now(timezone.utc)
    for tid in range(settings.queue_alert_len + 2):
        eng.ingest(Event.of("c", ZoneEnteredPayload(track_id=tid, zone="checkout"), ts=now))
    out = det.on_tick(eng, now)
    assert any(a.anomaly_type == AnomalyType.LONG_QUEUE for a in out)


def test_cooldown_debounces_repeats():
    det = AnomalyDetector(cooldown_sec=90)
    eng = AnalyticsEngine()
    now = datetime.now(timezone.utc)
    for tid in range(settings.queue_alert_len + 2):
        eng.ingest(Event.of("c", ZoneEnteredPayload(track_id=tid, zone="checkout"), ts=now))
    first = det.on_tick(eng, now)
    second = det.on_tick(eng, now + timedelta(seconds=5))  # within cooldown
    assert any(a.anomaly_type == AnomalyType.LONG_QUEUE for a in first)
    assert not any(a.anomaly_type == AnomalyType.LONG_QUEUE for a in second)

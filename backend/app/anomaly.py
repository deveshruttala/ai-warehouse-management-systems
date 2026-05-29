"""Anomaly detection engine.

Combines **rule-based** thresholds (operationally meaningful, explainable) with
**statistical** outlier detection (rolling-window z-score) over live metrics.

Detected anomalies:
  * ``zone_intrusion``  - presence in a restricted zone (event-driven, instant)
  * ``long_queue``      - checkout queue exceeds the configured length
  * ``crowd_surge``     - zone occupancy spikes (threshold OR z-score)
  * ``excessive_dwell`` - an individual lingers in a zone beyond a threshold
  * ``footfall_drop``   - per-minute entries collapse vs. recent baseline
  * ``statistical``     - generic z-score outlier on store occupancy

A per-(type, zone) cooldown debounces repeated alerts for the same condition.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from .analytics import AnalyticsEngine
from .config import settings
from .schemas import AnomalyPayload, AnomalyType, Event, EventType
from .pipeline.zones import RESTRICTED_ZONES


class RollingStat:
    """Maintains a rolling window and computes mean/std/z-score."""

    def __init__(self, window: int = 60):
        self.values: deque[float] = deque(maxlen=window)

    def push(self, v: float) -> None:
        self.values.append(v)

    @property
    def mean(self) -> float:
        return sum(self.values) / len(self.values) if self.values else 0.0

    @property
    def std(self) -> float:
        n = len(self.values)
        if n < 2:
            return 0.0
        m = self.mean
        var = sum((x - m) ** 2 for x in self.values) / (n - 1)
        return math.sqrt(var)

    def zscore(self, v: float) -> float:
        s = self.std
        return (v - self.mean) / s if s > 1e-9 else 0.0


class AnomalyDetector:
    def __init__(self, cooldown_sec: float = 90.0):
        self.cooldown = timedelta(seconds=cooldown_sec)
        self._last_fired: dict[tuple[str, str | None], datetime] = {}
        self._occ_stats: dict[str, RollingStat] = defaultdict(lambda: RollingStat(90))
        self._store_stat = RollingStat(120)
        self._minute_in_stat = RollingStat(30)
        self._dwell_fired: set[int] = set()
        self._last_minute: datetime | None = None

    # ------------------------------------------------------------------ #
    def _ready(self, atype: AnomalyType, zone: str | None, now: datetime) -> bool:
        key = (atype.value, zone)
        last = self._last_fired.get(key)
        if last and now - last < self.cooldown:
            return False
        self._last_fired[key] = now
        return True

    @staticmethod
    def _severity(observed: float, threshold: float) -> float:
        if threshold <= 0:
            return 0.5
        return max(0.0, min(1.0, (observed - threshold) / max(threshold, 1.0) + 0.5))

    # ------------------------------------------------------------------ #
    def on_event(self, event: Event) -> list[AnomalyPayload]:
        """Instant, event-driven detections."""
        out: list[AnomalyPayload] = []
        now = event.ts
        if event.event_type == EventType.ZONE_ENTERED and event.payload.zone in RESTRICTED_ZONES:
            zone = event.payload.zone
            if self._ready(AnomalyType.ZONE_INTRUSION, zone, now):
                out.append(
                    AnomalyPayload(
                        anomaly_type=AnomalyType.ZONE_INTRUSION,
                        zone=zone,
                        severity=0.95,
                        metric="restricted_presence",
                        observed=1,
                        expected=0,
                        message=f"Unauthorised presence detected in restricted zone '{zone}'.",
                    )
                )
        return out

    # ------------------------------------------------------------------ #
    def on_tick(self, engine: AnalyticsEngine, now: datetime | None = None) -> list[AnomalyPayload]:
        """Periodic detections over the live metric state."""
        now = now or datetime.now(timezone.utc)
        out: list[AnomalyPayload] = []

        # --- Long checkout queue (rule-based) ---
        qlen = engine.queue_length("checkout")
        if qlen >= settings.queue_alert_len and self._ready(AnomalyType.LONG_QUEUE, "checkout", now):
            out.append(
                AnomalyPayload(
                    anomaly_type=AnomalyType.LONG_QUEUE,
                    zone="checkout",
                    severity=self._severity(qlen, settings.queue_alert_len),
                    metric="queue_length",
                    observed=qlen,
                    expected=settings.queue_alert_len,
                    message=f"Checkout queue length {qlen} exceeds threshold {settings.queue_alert_len}.",
                )
            )

        # --- Crowd surge per zone (threshold OR z-score) ---
        for zone in ["skincare", "makeup", "fragrance", "promo", "checkout"]:
            occ = len(engine.zone_occupancy.get(zone, ()))
            stat = self._occ_stats[zone]
            z = stat.zscore(occ)
            mean = stat.mean
            stat.push(occ)
            surge = (
                occ >= settings.occupancy_alert
                or (occ >= 6 and z >= settings.anomaly_zscore)
                # Large absolute jump above baseline (robust when variance ~0).
                or (occ >= 8 and occ >= mean + 6)
            )
            if surge and self._ready(AnomalyType.CROWD_SURGE, zone, now):
                out.append(
                    AnomalyPayload(
                        anomaly_type=AnomalyType.CROWD_SURGE,
                        zone=zone,
                        severity=self._severity(occ, max(stat.mean, 6.0)),
                        metric="zone_occupancy",
                        observed=occ,
                        expected=round(stat.mean, 1),
                        message=f"Crowd surge in '{zone}': {occ} people (baseline ~{stat.mean:.1f}).",
                    )
                )

        # --- Excessive dwell (per active individual) ---
        for tid in list(engine.active_tracks):
            cur = engine.current_dwell(tid, now)
            if not cur:
                continue
            zone, dwell = cur
            if dwell >= settings.dwell_alert_sec and tid not in self._dwell_fired:
                self._dwell_fired.add(tid)
                out.append(
                    AnomalyPayload(
                        anomaly_type=AnomalyType.EXCESSIVE_DWELL,
                        zone=zone,
                        severity=self._severity(dwell, settings.dwell_alert_sec),
                        metric="dwell_sec",
                        observed=round(dwell, 1),
                        expected=settings.dwell_alert_sec,
                        message=f"Track {tid} has dwelled {dwell:.0f}s in '{zone}' (threshold {settings.dwell_alert_sec:.0f}s).",
                    )
                )
        # Forget dwell-fired tracks that are gone.
        self._dwell_fired &= engine.active_tracks

        # --- Statistical store-occupancy outlier ---
        occ = engine.store_occupancy
        zscore = self._store_stat.zscore(occ)
        self._store_stat.push(occ)
        if abs(zscore) >= settings.anomaly_zscore and len(self._store_stat.values) >= 30:
            if self._ready(AnomalyType.STATISTICAL, None, now):
                out.append(
                    AnomalyPayload(
                        anomaly_type=AnomalyType.STATISTICAL,
                        zone=None,
                        severity=min(1.0, abs(zscore) / (settings.anomaly_zscore * 2)),
                        metric="store_occupancy",
                        observed=occ,
                        expected=round(self._store_stat.mean, 1),
                        message=f"Store occupancy {occ} is a statistical outlier (z={zscore:.2f}).",
                    )
                )

        # --- Footfall drop (evaluated on minute rollover) ---
        minute = now.replace(second=0, microsecond=0)
        if self._last_minute is not None and minute > self._last_minute:
            prev = engine.buckets.get(self._last_minute)
            if prev is not None:
                entries = prev.footfall_in
                z = self._minute_in_stat.zscore(entries)
                if (
                    z <= -settings.anomaly_zscore
                    and len(self._minute_in_stat.values) >= 8
                    and self._minute_in_stat.mean >= 3
                    and self._ready(AnomalyType.FOOTFALL_DROP, "entrance", now)
                ):
                    out.append(
                        AnomalyPayload(
                            anomaly_type=AnomalyType.FOOTFALL_DROP,
                            zone="entrance",
                            severity=min(1.0, abs(z) / (settings.anomaly_zscore * 2)),
                            metric="footfall_in_per_min",
                            observed=entries,
                            expected=round(self._minute_in_stat.mean, 1),
                            message=f"Footfall dropped to {entries}/min (baseline ~{self._minute_in_stat.mean:.1f}/min). Possible entrance issue.",
                        )
                    )
                self._minute_in_stat.push(entries)
        self._last_minute = minute

        return out


_detector: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector

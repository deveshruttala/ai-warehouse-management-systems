# Event Schema Reference

All messages on the streaming bus and in the `events` table share one **envelope**.
Schema version: **`1.0`**.

## Envelope

```jsonc
{
  "schema_version": "1.0",          // string  — for forward/backward compatibility
  "event_id": "9f0c…",              // string  — unique idempotency key (uuid4 hex)
  "event_type": "zone.entered",     // enum    — see table below
  "camera_id": "cam-01",            // string  — source camera
  "ts": "2026-05-29T17:12:41.0Z",   // ISO-8601 UTC timestamp
  "payload": { "type": "zone.entered", … }  // discriminated on `type`
}
```

The `payload` is a **discriminated union** keyed on `payload.type` (which always
equals `event_type`). This lets consumers decode the correct typed structure
deterministically.

## Event types & payloads

| `event_type` | Payload fields | Meaning |
|--------------|----------------|---------|
| `track.started` | `track_id:int`, `bbox:{x,y,w,h,cx,cy}`, `confidence:float` | A new person is detected and tracked |
| `track.ended` | `track_id:int`, `duration_sec:float`, `last_zone:str?` | A track is lost / leaves the scene |
| `zone.entered` | `track_id:int`, `zone:str` | A track enters a configured zone |
| `zone.exited` | `track_id:int`, `zone:str`, `dwell_sec:float` | A track leaves a zone (with dwell time) |
| `line.crossed` | `track_id:int`, `line:str`, `direction:"in"\|"out"` | Directional crossing of a counting line (footfall) |
| `queue.update` | `zone:str`, `length:int`, `avg_wait_sec:float` | Queue state at a service zone |
| `occupancy.update` | `zone:str`, `count:int` | Occupancy count for a zone |
| `anomaly` | `anomaly_type`, `zone:str?`, `severity:0..1`, `metric:str`, `observed:float`, `expected:float?`, `message:str` | A detected anomaly |

### `anomaly_type` values

| Value | Trigger |
|-------|---------|
| `crowd_surge` | Per-zone occupancy spikes (threshold OR z-score vs. rolling baseline) |
| `long_queue` | Checkout queue length exceeds `SIS_QUEUE_ALERT_LEN` |
| `excessive_dwell` | An individual lingers in a zone beyond `SIS_DWELL_ALERT_SEC` |
| `zone_intrusion` | Presence detected in a restricted zone (instant) |
| `footfall_drop` | Per-minute entries collapse vs. recent baseline (z-score) |
| `statistical` | Generic z-score outlier on store occupancy |

## Examples

**Footfall entry**

```json
{
  "schema_version": "1.0",
  "event_id": "3b1f…",
  "event_type": "line.crossed",
  "camera_id": "cam-01",
  "ts": "2026-05-29T17:12:41.002Z",
  "payload": { "type": "line.crossed", "track_id": 42, "line": "entrance_line", "direction": "in" }
}
```

**Anomaly (long queue)**

```json
{
  "schema_version": "1.0",
  "event_id": "7c9a…",
  "event_type": "anomaly",
  "camera_id": "cam-01",
  "ts": "2026-05-29T17:12:41.7Z",
  "payload": {
    "type": "anomaly",
    "anomaly_type": "long_queue",
    "zone": "checkout",
    "severity": 0.62,
    "metric": "queue_length",
    "observed": 8,
    "expected": 6,
    "message": "Checkout queue length 8 exceeds threshold 6."
  }
}
```

## Versioning policy

- **Additive** changes (new optional fields, new event/anomaly types) keep
  `schema_version` at the same major and are backward compatible.
- **Breaking** changes bump the major (`2.0`). Consumers should branch on
  `schema_version` when handling mixed-version streams.

export interface ZoneStat {
  zone: string;
  occupancy: number;
  total_entries: number;
  avg_dwell_sec: number;
  queue_length: number | null;
  avg_wait_sec: number | null;
}

export interface LiveMetrics {
  ts: string;
  store_occupancy: number;
  footfall_in: number;
  footfall_out: number;
  active_tracks: number;
  zones: ZoneStat[];
  open_anomalies: number;
}

export interface Track {
  track_id: number;
  cx: number;
  cy: number;
  w: number;
  h: number;
}

export interface MetricsMessage {
  metrics: LiveMetrics;
  tracks: Track[];
}

export interface ZoneDef {
  name: string;
  label: string;
  kind: "area" | "queue" | "restricted";
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface LineDef {
  name: string;
  x: number;
  inward_is_right: boolean;
}

export interface Layout {
  zones: ZoneDef[];
  lines: LineDef[];
}

export interface Anomaly {
  id: number;
  ts: string;
  camera_id: string;
  anomaly_type: string;
  zone: string | null;
  severity: number;
  metric: string;
  observed: number;
  expected: number | null;
  message: string;
  acknowledged: boolean;
}

export interface DomainEvent {
  schema_version: string;
  event_id: string;
  event_type: string;
  camera_id: string;
  ts: string;
  payload: Record<string, unknown>;
}

export interface TimeBucket {
  bucket: string;
  footfall_in: number;
  footfall_out: number;
  avg_occupancy: number;
}

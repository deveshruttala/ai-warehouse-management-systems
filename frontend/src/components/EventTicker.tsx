import { fmtTime } from "../lib/format";
import type { DomainEvent } from "../types";

const TYPE_COLOR: Record<string, string> = {
  "track.started": "#38bdf8",
  "track.ended": "#64748b",
  "zone.entered": "#22c55e",
  "zone.exited": "#eab308",
  "line.crossed": "#a78bfa",
  "queue.update": "#f97316",
  "occupancy.update": "#14b8a6",
  anomaly: "#ef4444",
};

function describe(e: DomainEvent): string {
  const p = e.payload as Record<string, unknown>;
  switch (e.event_type) {
    case "track.started":
      return `Track #${p.track_id} started`;
    case "track.ended":
      return `Track #${p.track_id} ended (${Math.round(Number(p.duration_sec))}s)`;
    case "zone.entered":
      return `#${p.track_id} entered ${p.zone}`;
    case "zone.exited":
      return `#${p.track_id} left ${p.zone} (${Math.round(Number(p.dwell_sec))}s)`;
    case "line.crossed":
      return `#${p.track_id} crossed ${p.line} → ${p.direction}`;
    case "anomaly":
      return `${p.anomaly_type}: ${p.message}`;
    default:
      return e.event_type;
  }
}

export default function EventTicker({ events }: { events: DomainEvent[] }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Live Event Stream</h2>
      <div className="space-y-1 overflow-y-auto font-mono text-xs" style={{ maxHeight: 300 }}>
        {events.length === 0 && (
          <p className="py-6 text-center text-slate-500">Waiting for events…</p>
        )}
        {events.map((e) => (
          <div key={e.event_id} className="flex items-center gap-2 border-b border-slate-800/50 py-1">
            <span className="text-slate-600">{fmtTime(e.ts)}</span>
            <span
              className="rounded px-1.5 py-0.5 text-[10px]"
              style={{
                background: `${TYPE_COLOR[e.event_type] ?? "#475569"}22`,
                color: TYPE_COLOR[e.event_type] ?? "#94a3b8",
              }}
            >
              {e.event_type}
            </span>
            <span className="truncate text-slate-300">{describe(e)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

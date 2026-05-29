import { useCallback, useEffect, useRef, useState } from "react";
import { Radio } from "lucide-react";
import StatCards from "./components/StatCards";
import FloorMap from "./components/FloorMap";
import TrendChart from "./components/TrendChart";
import ZoneTable from "./components/ZoneTable";
import AnomalyPanel from "./components/AnomalyPanel";
import EventTicker from "./components/EventTicker";
import { useWebSocket, type WsStatus } from "./lib/useWebSocket";
import type { DomainEvent, Layout, LiveMetrics, MetricsMessage, Track } from "./types";

const STATUS_META: Record<WsStatus, { label: string; color: string }> = {
  open: { label: "Live", color: "#22c55e" },
  connecting: { label: "Connecting…", color: "#eab308" },
  closed: { label: "Disconnected", color: "#ef4444" },
};

export default function App() {
  const [layout, setLayout] = useState<Layout | null>(null);
  const [metrics, setMetrics] = useState<LiveMetrics | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [events, setEvents] = useState<DomainEvent[]>([]);
  const [anomalyPulse, setAnomalyPulse] = useState(0);
  const backend = useRef<string>("");

  useEffect(() => {
    fetch("/api/layout").then((r) => r.json()).then(setLayout).catch(() => {});
    fetch("/health").then((r) => r.json()).then((h) => (backend.current = h.detector_backend)).catch(() => {});
  }, []);

  const onMetrics = useCallback((msg: MetricsMessage) => {
    setMetrics(msg.metrics);
    setTracks(msg.tracks);
  }, []);

  const onEvent = useCallback((e: DomainEvent) => {
    setEvents((prev) => [e, ...prev].slice(0, 40));
    if (e.event_type === "anomaly") setAnomalyPulse((p) => p + 1);
  }, []);

  const status = useWebSocket<MetricsMessage>("/ws/metrics", onMetrics);
  useWebSocket<DomainEvent>("/ws/events", onEvent);

  const sm = STATUS_META[status];

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-5 py-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-violet-600 font-bold text-white">
            SI
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-100">Store Intelligence System</h1>
            <p className="text-xs text-slate-500">
              Real-time CCTV analytics · detection &amp; tracking · anomaly detection
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900 px-3 py-1.5">
            <Radio size={14} style={{ color: sm.color }} className={status === "open" ? "animate-pulse" : ""} />
            <span className="text-xs font-medium" style={{ color: sm.color }}>
              {sm.label}
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] space-y-4 px-5 py-5">
        <StatCards m={metrics} />

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="xl:col-span-2">
            <FloorMap layout={layout} tracks={tracks} metrics={metrics} />
          </div>
          <AnomalyPanel pulse={anomalyPulse} />
        </div>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <TrendChart />
          <ZoneTable m={metrics} />
        </div>

        <EventTicker events={events} />

        <footer className="pb-6 pt-2 text-center text-xs text-slate-600">
          Purplle Tech Challenge 2026 · Store Intelligence System · pipeline backend:{" "}
          <span className="text-slate-400">{backend.current || "—"}</span>
        </footer>
      </main>
    </div>
  );
}

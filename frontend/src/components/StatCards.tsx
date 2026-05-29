import { Activity, AlertTriangle, LogIn, LogOut, Users } from "lucide-react";
import type { LiveMetrics } from "../types";

function Card({
  icon,
  label,
  value,
  accent,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  accent: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 backdrop-blur">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">
          {label}
        </span>
        <span style={{ color: accent }}>{icon}</span>
      </div>
      <div className="mt-2 text-3xl font-semibold text-slate-100 tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export default function StatCards({ m }: { m: LiveMetrics | null }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <Card
        icon={<Users size={18} />}
        label="Store Occupancy"
        value={m?.store_occupancy ?? "—"}
        accent="#38bdf8"
        sub="people on sales floor"
      />
      <Card
        icon={<LogIn size={18} />}
        label="Footfall In"
        value={m?.footfall_in ?? "—"}
        accent="#22c55e"
        sub="cumulative entries"
      />
      <Card
        icon={<LogOut size={18} />}
        label="Footfall Out"
        value={m?.footfall_out ?? "—"}
        accent="#f97316"
        sub="cumulative exits"
      />
      <Card
        icon={<Activity size={18} />}
        label="Active Tracks"
        value={m?.active_tracks ?? "—"}
        accent="#a78bfa"
        sub="people being tracked"
      />
      <Card
        icon={<AlertTriangle size={18} />}
        label="Open Anomalies"
        value={m?.open_anomalies ?? "—"}
        accent="#ef4444"
        sub="awaiting acknowledgement"
      />
    </div>
  );
}

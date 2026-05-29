import { useCallback, useEffect, useState } from "react";
import { Check, ShieldAlert } from "lucide-react";
import { ANOMALY_META, fmtTime, severityColor } from "../lib/format";
import type { Anomaly } from "../types";

export default function AnomalyPanel({ pulse }: { pulse: number }) {
  const [items, setItems] = useState<Anomaly[]>([]);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/anomalies?limit=40");
      setItems(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, pulse]);

  const ack = async (id: number) => {
    await fetch(`/api/anomalies/${id}/ack`, { method: "POST" });
    setItems((prev) => prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a)));
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3 flex items-center gap-2">
        <ShieldAlert size={16} className="text-red-400" />
        <h2 className="text-sm font-semibold text-slate-200">Anomaly Alerts</h2>
        <span className="ml-auto rounded-full bg-red-500/15 px-2 py-0.5 text-xs text-red-300">
          {items.filter((a) => !a.acknowledged).length} open
        </span>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto pr-1" style={{ maxHeight: 360 }}>
        {items.length === 0 && (
          <p className="py-8 text-center text-sm text-slate-500">No anomalies detected yet.</p>
        )}
        {items.map((a) => {
          const meta = ANOMALY_META[a.anomaly_type] ?? { label: a.anomaly_type, color: "#94a3b8" };
          return (
            <div
              key={a.id}
              className={`rounded-lg border p-3 transition ${
                a.acknowledged
                  ? "border-slate-800 bg-slate-900/40 opacity-50"
                  : "border-slate-700 bg-slate-800/40"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase"
                  style={{ background: `${meta.color}22`, color: meta.color }}
                >
                  {meta.label}
                </span>
                {a.zone && (
                  <span className="text-xs capitalize text-slate-400">{a.zone}</span>
                )}
                <span className="ml-auto text-[11px] text-slate-500">{fmtTime(a.ts)}</span>
              </div>
              <p className="mt-1.5 text-xs text-slate-300">{a.message}</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-[11px] text-slate-500">severity</span>
                <span className="h-1.5 w-16 overflow-hidden rounded bg-slate-800">
                  <span
                    className="block h-full rounded"
                    style={{ width: `${a.severity * 100}%`, background: severityColor(a.severity) }}
                  />
                </span>
                {!a.acknowledged && (
                  <button
                    onClick={() => ack(a.id)}
                    className="ml-auto flex items-center gap-1 rounded-md border border-slate-700 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-700/50"
                  >
                    <Check size={12} /> Acknowledge
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

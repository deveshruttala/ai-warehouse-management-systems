import { useEffect, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtHM } from "../lib/format";
import type { TimeBucket } from "../types";

export default function TrendChart() {
  const [data, setData] = useState<TimeBucket[]>([]);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const res = await fetch("/api/analytics/history?minutes=60");
        const json: TimeBucket[] = await res.json();
        if (active) setData(json);
      } catch {
        /* ignore */
      }
    };
    load();
    const id = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  const chartData = data.map((d) => ({
    t: fmtHM(d.bucket),
    in: d.footfall_in,
    out: d.footfall_out,
    occ: d.avg_occupancy,
  }));

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">
        Footfall &amp; Occupancy — last 60 min
      </h2>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="occFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="t" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={24} />
          <YAxis tick={{ fill: "#64748b", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              background: "#0f172a",
              border: "1px solid #1e293b",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area
            type="monotone"
            dataKey="occ"
            name="Avg occupancy"
            stroke="#38bdf8"
            fill="url(#occFill)"
            strokeWidth={2}
          />
          <Line type="monotone" dataKey="in" name="Entries/min" stroke="#22c55e" dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="out" name="Exits/min" stroke="#f97316" dot={false} strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

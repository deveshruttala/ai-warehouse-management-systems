import type { LiveMetrics } from "../types";

export default function ZoneTable({ m }: { m: LiveMetrics | null }) {
  const zones = m?.zones ?? [];
  const maxOcc = Math.max(1, ...zones.map((z) => z.occupancy));

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">Zone Analytics</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2 pr-2 font-medium">Zone</th>
              <th className="pb-2 pr-2 font-medium">Occupancy</th>
              <th className="pb-2 pr-2 font-medium">Entries</th>
              <th className="pb-2 pr-2 font-medium">Avg dwell</th>
              <th className="pb-2 font-medium">Queue / wait</th>
            </tr>
          </thead>
          <tbody>
            {zones.map((z) => (
              <tr key={z.zone} className="border-t border-slate-800/70">
                <td className="py-2 pr-2 capitalize text-slate-300">{z.zone}</td>
                <td className="py-2 pr-2">
                  <div className="flex items-center gap-2">
                    <span className="w-6 tabular-nums text-slate-200">{z.occupancy}</span>
                    <span className="h-1.5 w-20 overflow-hidden rounded bg-slate-800">
                      <span
                        className="block h-full rounded bg-sky-400"
                        style={{ width: `${(z.occupancy / maxOcc) * 100}%` }}
                      />
                    </span>
                  </div>
                </td>
                <td className="py-2 pr-2 tabular-nums text-slate-400">{z.total_entries}</td>
                <td className="py-2 pr-2 tabular-nums text-slate-400">{z.avg_dwell_sec}s</td>
                <td className="py-2 tabular-nums text-slate-400">
                  {z.queue_length != null ? `${z.queue_length} · ${z.avg_wait_sec}s` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

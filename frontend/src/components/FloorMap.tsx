import type { Layout, LiveMetrics, Track } from "../types";

const ZONE_STYLE: Record<string, { fill: string; stroke: string }> = {
  area: { fill: "rgba(56,189,248,0.07)", stroke: "rgba(56,189,248,0.45)" },
  queue: { fill: "rgba(234,179,8,0.10)", stroke: "rgba(234,179,8,0.55)" },
  restricted: { fill: "rgba(239,68,68,0.12)", stroke: "rgba(239,68,68,0.6)" },
};

const W = 1000;
const H = 620;

export default function FloorMap({
  layout,
  tracks,
  metrics,
}: {
  layout: Layout | null;
  tracks: Track[];
  metrics: LiveMetrics | null;
}) {
  const occ = new Map(metrics?.zones.map((z) => [z.zone, z.occupancy]) ?? []);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-200">Live Floor Map</h2>
        <span className="text-xs text-slate-500">{tracks.length} tracked · cam-01</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded-lg bg-slate-950/60">
        {/* zones */}
        {layout?.zones.map((z) => {
          const s = ZONE_STYLE[z.kind] ?? ZONE_STYLE.area;
          const x = z.x0 * W;
          const y = z.y0 * H;
          const w = (z.x1 - z.x0) * W;
          const h = (z.y1 - z.y0) * H;
          return (
            <g key={z.name}>
              <rect
                x={x}
                y={y}
                width={w}
                height={h}
                rx={8}
                fill={s.fill}
                stroke={s.stroke}
                strokeWidth={1.5}
                strokeDasharray={z.kind === "restricted" ? "6 4" : undefined}
              />
              <text x={x + 8} y={y + 18} fill="#94a3b8" fontSize={13} fontWeight={600}>
                {z.label}
              </text>
              <text x={x + 8} y={y + 36} fill="#64748b" fontSize={12}>
                {occ.get(z.name) ?? 0} inside
              </text>
            </g>
          );
        })}

        {/* counting lines */}
        {layout?.lines.map((ln) => (
          <g key={ln.name}>
            <line
              x1={ln.x * W}
              y1={0}
              x2={ln.x * W}
              y2={H}
              stroke="#22c55e"
              strokeWidth={2}
              strokeDasharray="4 6"
            />
            <text x={ln.x * W + 6} y={H - 10} fill="#22c55e" fontSize={11}>
              {ln.name}
            </text>
          </g>
        ))}

        {/* tracks */}
        {tracks.map((t) => (
          <g key={t.track_id}>
            <circle cx={t.cx * W} cy={t.cy * H} r={7} fill="#38bdf8" opacity={0.9} />
            <circle cx={t.cx * W} cy={t.cy * H} r={12} fill="none" stroke="#38bdf8" opacity={0.3} />
          </g>
        ))}
      </svg>
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-400">
        <Legend color="rgba(56,189,248,0.6)" label="Sales aisle" />
        <Legend color="rgba(234,179,8,0.7)" label="Checkout (queue)" />
        <Legend color="rgba(239,68,68,0.7)" label="Restricted" />
        <Legend color="#22c55e" label="Counting line" />
        <Legend color="#38bdf8" label="Tracked person" dot />
      </div>
    </div>
  );
}

function Legend({ color, label, dot }: { color: string; label: string; dot?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="inline-block"
        style={{
          width: dot ? 10 : 14,
          height: dot ? 10 : 10,
          borderRadius: dot ? "50%" : 3,
          background: color,
        }}
      />
      {label}
    </span>
  );
}

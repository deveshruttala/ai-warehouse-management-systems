export const fmtTime = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

export const fmtHM = (iso: string): string => {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export const ANOMALY_META: Record<string, { label: string; color: string }> = {
  crowd_surge: { label: "Crowd Surge", color: "#f59e0b" },
  long_queue: { label: "Long Queue", color: "#ef4444" },
  excessive_dwell: { label: "Excessive Dwell", color: "#a855f7" },
  zone_intrusion: { label: "Zone Intrusion", color: "#dc2626" },
  footfall_drop: { label: "Footfall Drop", color: "#0ea5e9" },
  statistical: { label: "Statistical Outlier", color: "#14b8a6" },
};

export const severityColor = (s: number): string =>
  s >= 0.75 ? "#ef4444" : s >= 0.45 ? "#f59e0b" : "#eab308";

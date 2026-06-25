import type {
  Config, Status, Signal, JournalRow, PairOverview, ModelInfo, DataInfo, BacktestRow, Analysis,
} from "./types";

/** Same-origin → Next.js proxy → Python API. Works on Railway with runtime API_URL. */
const BASE =
  typeof window !== "undefined"
    ? ""
    : process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  base: BASE,
  config: () => j<Config>("/api/config"),
  status: () => j<Status & { seed_state?: string }>("/api/status"),
  signals: () => j<{ signals: Signal[]; seed_state?: string }>("/api/signals"),
  overview: () => j<{ overview: PairOverview[]; seed_state?: string }>("/api/overview"),
  journal: (n = 60) => j<{ rows: JournalRow[]; count?: number; entries?: number; closes?: number; last_ts?: string | null }>(`/api/journal?n=${n}`),
  model: () => j<ModelInfo>("/api/model"),
  data: () => j<DataInfo>("/api/data"),
  analysis: (pair: string, tf?: string) => j<Analysis>(`/api/analysis?pair=${pair}${tf ? `&tf=${tf}` : ""}`),
  chartUrl: (pair: string, tf: string, bust = 0, signal?: Partial<Signal>) => {
    if (!signal?.entry) return `${BASE}/api/chart?pair=${pair}&tf=${tf}&t=${bust}`;
    const q = new URLSearchParams({
      pair,
      tf,
      entry: String(signal.entry),
      stop: String(signal.stop!),
      target: String(signal.target!),
      dir: signal.direction || "long",
      t: String(bust),
    });
    if (signal.bar_idx != null) q.set("bar", String(signal.bar_idx));
    if (signal.zone_top != null) q.set("zt", String(signal.zone_top));
    if (signal.zone_bottom != null) q.set("zb", String(signal.zone_bottom));
    if (signal.zone_kind) q.set("zk", signal.zone_kind);
    if (signal.confluences?.length) q.set("notes", signal.confluences.slice(0, 7).join("|"));
    return `${BASE}/api/chart?${q.toString()}`;
  },
  signalChartUrl: (s: Signal, bust = 0) => api.chartUrl(s.pair, s.tf || "H4", bust, s),
  backtest: (pair?: string) =>
    j<{ results: BacktestRow[]; seed_state?: string }>(`/api/backtest${pair ? `?pair=${pair}` : ""}`),
  tick: (refresh = false) =>
    j<Status>(`/api/tick?refresh=${refresh ? 1 : 0}`, { method: "POST" }),
};

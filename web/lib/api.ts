import type {
  Config, Status, Signal, JournalRow, PairOverview, ModelInfo, DataInfo, BacktestRow, Analysis,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  journal: (n = 60) => j<{ rows: JournalRow[] }>(`/api/journal?n=${n}`),
  model: () => j<ModelInfo>("/api/model"),
  data: () => j<DataInfo>("/api/data"),
  analysis: (pair: string) => j<Analysis>(`/api/analysis?pair=${pair}`),
  chartUrl: (pair: string, tf: string, bust = 0) => `${BASE}/api/chart?pair=${pair}&tf=${tf}&t=${bust}`,
  backtest: (pair?: string) =>
    j<{ results: BacktestRow[]; seed_state?: string }>(`/api/backtest${pair ? `?pair=${pair}` : ""}`),
  tick: (refresh = false) =>
    j<Status>(`/api/tick?refresh=${refresh ? 1 : 0}`, { method: "POST" }),
};


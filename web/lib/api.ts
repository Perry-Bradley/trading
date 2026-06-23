import type { Config, Status, Signal, JournalRow } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", ...init });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

export const api = {
  base: BASE,
  config: () => j<Config>("/api/config"),
  status: () => j<Status>("/api/status"),
  signals: () => j<{ signals: Signal[] }>("/api/signals"),
  journal: (n = 60) => j<{ rows: JournalRow[] }>(`/api/journal?n=${n}`),
  tick: (refresh = false) =>
    j<Status>(`/api/tick?refresh=${refresh ? 1 : 0}`, { method: "POST" }),
};

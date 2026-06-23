"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/useLive";
import type { BacktestRow, Config } from "@/lib/types";
import { Section } from "@/components/ui";

export default function Performance() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [rows, setRows] = useState<BacktestRow[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const c = await api.config().catch(() => null);
    if (c) setCfg(c);
  }, []);
  useLive(load, 60000);

  const runAll = async () => {
    setBusy(true);
    try { const r = await api.backtest(); setRows(r.results || []); } finally { setBusy(false); }
  };

  const tot = rows.reduce((a, r) => a + (r.total_r || 0), 0);
  const trades = rows.reduce((a, r) => a + (r.trades || 0), 0);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h1 className="text-xl font-bold">Performance — backtest</h1>
        <button onClick={runAll} disabled={busy}
          className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-50">
          {busy ? "Testing all pairs…" : "Run backtest (all pairs)"}
        </button>
      </div>
      <p className="text-sub text-sm">
        Causal, costs-included backtest of the MSNR model on history ({cfg?.tf}/{cfg?.bias_tf}, {cfg?.target_r}R target).
        These are <b>honest</b> numbers — no lookahead, spread &amp; slippage subtracted, stop-first on ambiguity.
      </p>

      {rows.length === 0 ? (
        <Section title="No results yet"><p className="text-sub text-sm py-2">Press “Run backtest” to test every pair (takes ~10–20s).</p></Section>
      ) : (
        <Section title={`Results — ${trades} trades, ${tot >= 0 ? "+" : ""}${tot.toFixed(1)}R total`}>
          <div className="scroll-x">
            <table className="w-full text-sm min-w-[720px]">
              <thead><tr className="text-sub text-xs text-left border-b border-line">
                <th className="py-2 pr-3">Pair</th><th className="pr-3">Trades</th><th className="pr-3">Win%</th>
                <th className="pr-3">Breakeven</th><th className="pr-3">Expectancy</th><th className="pr-3">Total R</th>
                <th className="pr-3">PF</th><th className="pr-3">Max DD</th>
              </tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-b border-line/70">
                    <td className="py-2.5 pr-3 font-semibold">{r.pair}</td>
                    {r.error ? <td className="text-sub" colSpan={7}>{r.error}</td> : <>
                      <td className="pr-3">{r.trades}</td>
                      <td className={`pr-3 font-semibold ${r.win_rate >= r.breakeven_wr ? "text-up" : "text-down"}`}>{(r.win_rate * 100).toFixed(1)}%</td>
                      <td className="pr-3 text-sub">{(r.breakeven_wr * 100).toFixed(0)}%</td>
                      <td className={`pr-3 ${r.expectancy_r >= 0 ? "text-up" : "text-down"}`}>{r.expectancy_r >= 0 ? "+" : ""}{r.expectancy_r.toFixed(3)}R</td>
                      <td className={`pr-3 font-semibold ${r.total_r >= 0 ? "text-up" : "text-down"}`}>{r.total_r >= 0 ? "+" : ""}{r.total_r.toFixed(1)}R</td>
                      <td className="pr-3">{r.profit_factor?.toFixed(2) ?? "∞"}</td>
                      <td className="pr-3 text-down">{r.max_dd_r.toFixed(1)}R</td>
                    </>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  );
}

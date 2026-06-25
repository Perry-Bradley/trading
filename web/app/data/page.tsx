"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/useLive";
import type { DataInfo } from "@/lib/types";
import { Section } from "@/components/ui";

export default function DataPage() {
  const [d, setD] = useState<DataInfo | null>(null);
  const load = useCallback(async () => { try { setD(await api.data()); } catch { /* */ } }, []);
  useLive(load, 60000);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Data pipeline</h1>
      <p className="text-sub text-sm">
        OHLCV for every pair across the MSNR ladder <b>{d?.ladder || "D1→H4→H1→M30"}</b>, fetched from{" "}
        <b>{d?.source || "live sources"}</b>, sanitised for OHLC integrity — the foundation the
        detectors, backtester and model all read from.
      </p>

      {d?.finnhub && (
        <Section title="Finnhub live stream" right={
          <span className={`text-xs font-medium ${d.finnhub.connected ? "text-up" : "text-down"}`}>
            {d.finnhub.connected ? "WebSocket connected" : "WebSocket offline"}
          </span>
        }>
          <p className="text-sub text-sm mb-3">
            Forex/gold uses <b>Finnhub WebSocket</b> for live ticks (forming candles + dashboard prices)
            and <b>REST</b> for historical analysis. Set{" "}
            <code className="bg-canvas px-1 rounded text-xs">FINNHUB_KEY</code> on the API service.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm mb-3">
            <div><span className="text-sub text-xs">Trades received</span><div className="font-semibold">{d.finnhub.trades.toLocaleString()}</div></div>
            <div><span className="text-sub text-xs">Last tick</span><div className="font-mono text-xs">{d.finnhub.last_trade || "—"}</div></div>
          </div>
          {d.finnhub.last_error && !d.finnhub.connected && (
            <p className="text-down text-sm mb-2">{d.finnhub.last_error}</p>
          )}
          {Object.keys(d.finnhub.quotes || {}).length > 0 && (
            <ul className="text-sm space-y-1">
              {Object.entries(d.finnhub.quotes).map(([p, px]) => (
                <li key={p} className="flex justify-between font-mono text-xs py-0.5">
                  <span>{p}</span><span>{px}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      {d && d.pairs.some((p) => !p.live) && (
        <div className="p-3 rounded-xl bg-warn/5 border border-warn/30 text-warn text-sm">
          Forex needs <code className="bg-canvas px-1 rounded">FINNHUB_KEY</code> on the API service.
          Crypto uses Binance; V100/V25 use Deriv — both live with no extra key.
        </div>
      )}
      <Section title="Coverage" right={<span className="text-sub text-xs">{d?.pairs.length ?? 0} pairs · {d?.timeframes.length ?? 0} timeframes</span>}>
        {!d ? <p className="text-sub text-sm py-2">Loading…</p> : (
          <div className="scroll-x">
            <table className="w-full text-sm min-w-[760px]">
              <thead><tr className="text-sub text-xs text-left border-b border-line">
                <th className="py-2 pr-3">Pair</th><th className="pr-3">Source</th>
                {d.timeframes.map((t) => <th key={t} className="pr-3">{t}</th>)}
              </tr></thead>
              <tbody>
                {d.pairs.map((p) => (
                  <tr key={p.pair} className="border-b border-line/70">
                    <td className="py-2.5 pr-3 font-semibold">{p.pair}</td>
                    <td className="pr-3">
                      <span className={`text-[11px] px-2 py-0.5 rounded-full ${p.live ? "bg-up/10 text-up" : "bg-line text-sub"}`}>
                        {p.source}{p.live ? " · live" : " · delayed"}
                      </span>
                    </td>
                    {d.timeframes.map((t) => {
                      const c = p.tf[t];
                      return (
                        <td key={t} className="pr-3">
                          {c ? <div><div className="font-mono">{c.bars.toLocaleString()}</div>
                            <div className="text-[11px] text-sub">{c.start} → {c.end}</div></div>
                            : <span className="text-sub">—</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="Pipeline stages">
        <ol className="text-sm text-ink/80 space-y-1.5 list-decimal pl-5">
          <li><b>Fetch</b> — pull OHLCV per pair/timeframe (free yfinance; ~15-min delayed).</li>
          <li><b>Sanitise</b> — clamp bars where the high/low don&apos;t bracket open/close.</li>
          <li><b>Detect</b> — market structure, SNR zones, rejections, order blocks, FVGs, sweeps.</li>
          <li><b>Scan + score</b> — combine into setups, score with the model, size by confidence.</li>
          <li><b>Backtest / learn</b> — measure expectancy on history; learn from each closed paper trade.</li>
        </ol>
        <p className="text-warn text-xs mt-3">
          Note: yfinance intraday history is limited (H1/H4 ≈ 2y, M30 ≈ 2mo). For deeper data &amp; true live
          feeds, a broker source (MT5 / Binance) is the upgrade path.
        </p>
      </Section>
    </div>
  );
}

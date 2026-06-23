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
        <b>{d?.source || "yfinance"}</b>, sanitised for OHLC integrity, then resampled (H4) — the foundation the
        detectors, backtester and model all read from.
      </p>

      {d && d.pairs.some((p) => !p.live) && (
        <div className="p-3 rounded-xl bg-warn/5 border border-warn/30 text-warn text-sm">
          Forex pairs show <b>yfinance (delayed ~15 min)</b> because no Twelve Data key is set.
          For <b>live forex</b>: grab a free key at twelvedata.com, then set <code className="bg-canvas px-1 rounded">TWELVEDATA_KEY</code>
          on the API service and redeploy. Crypto (Binance) is already live, no key needed.
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

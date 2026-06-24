"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLive, fmtPrice } from "@/lib/useLive";
import type { Config, Analysis, BacktestRow, Zone } from "@/lib/types";
import { DirBadge, Section, Chip } from "@/components/ui";

function ZoneList({ items, color }: { items: Zone[]; color?: string }) {
  if (!items?.length) return <p className="text-sub text-sm py-1">none</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((z, i) => (
        <li key={i} className="flex items-center justify-between text-sm">
          <span className={`font-medium ${z.kind?.includes("bull") || z.kind === "support" ? "text-up" : "text-down"}`}>
            {z.kind}
          </span>
          <span className="font-mono text-xs text-sub">{fmtPrice(z.bottom)}–{fmtPrice(z.top)} · {z.time}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Pairs() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [sel, setSel] = useState<string>("");
  const [selTf, setSelTf] = useState<string>("");
  const [a, setA] = useState<Analysis | null>(null);
  const [bt, setBt] = useState<BacktestRow | null>(null);
  const [btBusy, setBtBusy] = useState(false);
  const [bust, setBust] = useState(0);
  const [analysisErr, setAnalysisErr] = useState<string | null>(null);

  useEffect(() => {
    api.config().then((c) => {
      setCfg(c);
      const sp = new URLSearchParams(window.location.search);
      const p = sp.get("p");
      const tf = sp.get("tf");
      setSel(p && c.pairs.includes(p) ? p : c.pairs[0]);
      setSelTf(tf && ["H4", "H1", "M30"].includes(tf) ? tf : c.tf);
    }).catch(() => {});
  }, []);

  const [analysisErr, setAnalysisErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!sel || !selTf) return;
    try {
      setAnalysisErr(null);
      setA(await api.analysis(sel, selTf));
      setBust(Date.now());
    } catch (e: any) {
      setAnalysisErr(e?.message ?? "Failed to load analysis");
    }
  }, [sel, selTf]);
  useLive(load);

  const runBt = async () => {
    if (!sel) return;
    setBtBusy(true);
    try { const r = await api.backtest(sel); setBt(r.results?.[0] ?? null); } finally { setBtBusy(false); }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Pairs — chart & analysis</h1>

      <div className="flex gap-2 scroll-x pb-1">
        {(cfg?.pairs ?? []).map((p) => (
          <Chip key={p} active={sel === p} onClick={() => { setSel(p); setBt(null); }}>{p}</Chip>
        ))}
      </div>

      {a && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-2xl font-bold">{a.pair}</span>
            <div className="flex gap-1 ml-2 bg-line/20 p-1 rounded-lg">
              {["H4", "H1", "M30"].map(t => (
                <button key={t} onClick={() => { setSelTf(t); setA(null); }} className={`px-2 py-0.5 text-xs font-bold rounded ${selTf === t ? "bg-brand text-white" : "text-sub hover:text-ink"}`}>{t}</button>
              ))}
            </div>
            <DirBadge dir={a.bias} />
            <span className="text-sub text-sm">price <b className="font-mono text-ink">{fmtPrice(a.price)}</b> · {a.tf}/{a.bias_tf} bias</span>
            <button onClick={runBt} disabled={btBusy}
              className="ml-auto px-3.5 py-1.5 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-50">
              {btBusy ? "Testing…" : "Backtest this pair"}
            </button>
          </div>

          {bt && !bt.error && (
            <Section title={`Backtest — ${bt.pair} (${cfg?.tf}/${cfg?.bias_tf}, ${cfg?.target_r}R)`}>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div><div className="text-sub text-xs">Trades</div><div className="font-semibold">{bt.trades}</div></div>
                <div><div className="text-sub text-xs">Win rate</div><div className={`font-semibold ${bt.win_rate >= bt.breakeven_wr ? "text-up" : "text-down"}`}>{(bt.win_rate * 100).toFixed(1)}% <span className="text-sub font-normal">/ be {(bt.breakeven_wr * 100).toFixed(0)}%</span></div></div>
                <div><div className="text-sub text-xs">Expectancy</div><div className={`font-semibold ${bt.expectancy_r >= 0 ? "text-up" : "text-down"}`}>{bt.expectancy_r >= 0 ? "+" : ""}{bt.expectancy_r.toFixed(3)}R</div></div>
                <div><div className="text-sub text-xs">Total</div><div className={`font-semibold ${bt.total_r >= 0 ? "text-up" : "text-down"}`}>{bt.total_r >= 0 ? "+" : ""}{bt.total_r.toFixed(1)}R</div></div>
                <div><div className="text-sub text-xs">Profit factor</div><div className="font-semibold">{bt.profit_factor?.toFixed(2) ?? "∞"}</div></div>
                <div><div className="text-sub text-xs">Max drawdown</div><div className="font-semibold text-down">{bt.max_dd_r.toFixed(1)}R</div></div>
                <div><div className="text-sub text-xs">Avg win</div><div className="font-semibold text-up">+{bt.avg_win_r.toFixed(2)}R</div></div>
                <div><div className="text-sub text-xs">Avg loss</div><div className="font-semibold text-down">{bt.avg_loss_r.toFixed(2)}R</div></div>
              </div>
            </Section>
          )}

          <Section title="Annotated chart" right={<span className="text-sub text-xs">SNR zones · structure · rejections</span>}>
            {cfg && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                key={`${a.pair}-${selTf}-${bust}`}
                src={api.chartUrl(a.pair, selTf || a.tf, bust)}
                alt={`${a.pair} chart`}
                className="w-full rounded-xl border border-line bg-surface"
                onError={(e) => { (e.target as HTMLImageElement).alt = `Chart unavailable for ${a.pair} ${selTf} — data is being fetched in the background`; }}
              />
            )}
          </Section>

          <div className="grid lg:grid-cols-2 gap-4">
            <Section title="Quasimodo (QML) — premium reversals">
              {a.quasimodos.length === 0 ? <p className="text-sub text-sm">none recently</p> : (
                <ul className="space-y-1.5">
                  {a.quasimodos.map((q, i) => (
                    <li key={i} className="flex items-center justify-between text-sm">
                      <span className={`font-semibold ${q.kind === "bullish" ? "text-up" : "text-down"}`}>{q.kind} QM</span>
                      <span className="font-mono text-xs text-sub">sweep {fmtPrice(q.sweep)} → CHoCH {fmtPrice(q.choch)} · {q.time}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title="Breaker blocks"><ZoneList items={a.breakers} /></Section>
            <Section title="Structure (BOS / CHoCH)">
              {a.breaks.length === 0 ? <p className="text-sub text-sm">none</p> : (
                <ul className="space-y-1.5">
                  {a.breaks.map((b, i) => (
                    <li key={i} className="flex items-center justify-between text-sm">
                      <span className={`font-medium ${b.type === "CHoCH" ? "text-brand" : "text-ink"}`}>{b.type} {b.dir === "up" ? "↑" : "↓"}</span>
                      <span className="font-mono text-xs text-sub">{fmtPrice(b.level)} · {b.time}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title="Liquidity sweeps (BSL / SSL)">
              {a.sweeps.length === 0 ? <p className="text-sub text-sm">none</p> : (
                <ul className="space-y-1.5">
                  {a.sweeps.map((s, i) => (
                    <li key={i} className="flex items-center justify-between text-sm">
                      <span className={`font-medium ${s.side === "SSL" ? "text-up" : "text-down"}`}>{s.side} swept</span>
                      <span className="font-mono text-xs text-sub">{fmtPrice(s.level)} · {s.time}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title="Fresh SNR levels"><ZoneList items={a.fresh_snr} /></Section>
            <Section title="Order blocks"><ZoneList items={a.order_blocks} /></Section>
            <Section title="Fair value gaps"><ZoneList items={a.fvgs} /></Section>
          </div>
        </>
      )}
    </div>
  );
}

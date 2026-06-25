"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useLive, fmtPrice } from "@/lib/useLive";
import type { Config, Analysis, BacktestRow, Zone, Signal } from "@/lib/types";
import { DirBadge, Section, Chip } from "@/components/ui";
import { TradingViewChart } from "@/components/TradingViewChart";

function ZoneList({ items }: { items: Zone[] }) {
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

function parseSignalFromUrl(): Partial<Signal> | null {
  if (typeof window === "undefined") return null;
  const sp = new URLSearchParams(window.location.search);
  const entry = sp.get("entry");
  if (!entry) return null;
  return {
    pair: sp.get("p") || "",
    tf: sp.get("tf") || "H4",
    direction: (sp.get("dir") as "long" | "short") || "long",
    entry: parseFloat(entry),
    stop: parseFloat(sp.get("stop") || "0"),
    target: parseFloat(sp.get("target") || "0"),
    bar_idx: sp.get("bar") ? parseInt(sp.get("bar")!, 10) : undefined,
    zone_top: sp.get("zt") ? parseFloat(sp.get("zt")!) : undefined,
    zone_bottom: sp.get("zb") ? parseFloat(sp.get("zb")!) : undefined,
    zone_kind: sp.get("zk") || undefined,
    confluences: sp.get("notes")?.split("|").filter(Boolean),
  };
}

export default function Pairs() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [sel, setSel] = useState("EURUSD");
  const [selTf, setSelTf] = useState("H4");
  const [a, setA] = useState<Analysis | null>(null);
  const [bt, setBt] = useState<BacktestRow | null>(null);
  const [btBusy, setBtBusy] = useState(false);
  const [bust, setBust] = useState(0);
  const [loading, setLoading] = useState(true);
  const [analysisErr, setAnalysisErr] = useState<string | null>(null);
  const [urlSignal, setUrlSignal] = useState<Partial<Signal> | null>(null);
  const [chartMode, setChartMode] = useState<"live" | "analysis">("live");

  useEffect(() => {
    api.config().then((c) => {
      setCfg(c);
      const sp = new URLSearchParams(window.location.search);
      const p = sp.get("p");
      const tf = sp.get("tf");
      if (p && c.pairs.includes(p)) setSel(p);
      if (tf && ["H4", "H1", "M30"].includes(tf)) setSelTf(tf);
      else setSelTf(c.tf);
    }).catch(() => {
      setAnalysisErr("Cannot reach API — start the backend: python -m src.webapp.app");
    });
    const sig = parseSignalFromUrl();
    setUrlSignal(sig);
    if (sig?.entry) setChartMode("analysis");
  }, []);

  const load = useCallback(async () => {
    if (!sel || !selTf) return;
    setLoading(true);
    setAnalysisErr(null);
    try {
      setA(await api.analysis(sel, selTf));
      setBust(Date.now());
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load analysis";
      setAnalysisErr(`${msg}. Is the Python API running on port 8000?`);
      setA(null);
    } finally {
      setLoading(false);
    }
  }, [sel, selTf]);
  useLive(load, 20000);

  const runBt = async () => {
    if (!sel) return;
    setBtBusy(true);
    try {
      const r = await api.backtest(sel);
      setBt(r.results?.[0] ?? null);
    } finally {
      setBtBusy(false);
    }
  };

  const pairs = cfg?.pairs ?? ["EURUSD", "GBPUSD", "AUDUSD", "XAUUSD", "BTCUSD", "V100", "V25"];
  const chartSignal = urlSignal?.entry ? urlSignal : undefined;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Pairs — chart & analysis</h1>
      <p className="text-sub text-sm">
        Live TradingView chart plus annotated MSNR analysis (SNR zones, OB, BB, QM, BSL/SSL, FVG).
        Analysis panels refresh every 20s from parquet data.
      </p>

      <div className="flex gap-2 scroll-x pb-1">
        {pairs.map((p) => (
          <Chip key={p} active={sel === p} onClick={() => { setSel(p); setBt(null); setUrlSignal(null); }}>
            {p}
          </Chip>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <span className="text-2xl font-bold">{sel}</span>
        <div className="flex gap-1 bg-line/20 p-1 rounded-lg">
          {["H4", "H1", "M30"].map((t) => (
            <button
              key={t}
              onClick={() => { setSelTf(t); setA(null); }}
              className={`px-2 py-0.5 text-xs font-bold rounded ${selTf === t ? "bg-brand text-white" : "text-sub hover:text-ink"}`}
            >
              {t}
            </button>
          ))}
        </div>
        {a && <DirBadge dir={a.bias} />}
        {a && (
          <span className="text-sub text-sm">
            price <b className="font-mono text-ink">{fmtPrice(a.price)}</b> · {a.tf}/{a.bias_tf} bias
            {a.now_utc && (
              <> · now <b className="font-mono text-ink">{a.now_utc}</b></>
            )}
            {a.last_bar && (
              <> · last bar <b className="font-mono text-ink">{a.last_bar}</b></>
            )}
          </span>
        )}
        {a && a.stale_minutes != null && a.stale_minutes > 60 && (
          <span className="text-[11px] text-amber-400/90">
            data {a.stale_minutes}m stale — refreshing on next load
          </span>
        )}
        <button
          onClick={runBt}
          disabled={btBusy || loading}
          className="ml-auto px-3.5 py-1.5 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-50"
        >
          {btBusy ? "Testing…" : "Backtest this pair"}
        </button>
      </div>

      {analysisErr && (
        <div className="p-3 rounded-xl bg-down/5 border border-down/30 text-down text-sm">
          {analysisErr}
        </div>
      )}

      <Section
        title={chartSignal ? "Signal chart — zoomed to setup" : chartMode === "live" ? "Live chart" : "Annotated chart"}
        right={
          <div className="flex items-center gap-2">
            {!chartSignal && (
              <div className="flex gap-1 bg-line/20 p-0.5 rounded-lg">
                {(["live", "analysis"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setChartMode(m)}
                    className={`px-2 py-0.5 text-[10px] font-bold rounded ${chartMode === m ? "bg-brand text-white" : "text-sub hover:text-ink"}`}
                  >
                    {m === "live" ? "TradingView" : "MSNR overlay"}
                  </button>
                ))}
              </div>
            )}
            <span className="text-sub text-xs hidden sm:inline">SNR · OB · BB · QM · BSL/SSL · FVG</span>
          </div>
        }
      >
        {chartSignal || chartMode === "analysis" ? (
          loading && !bust ? (
            <div className="py-16 text-center text-sub text-sm">Loading chart for {sel} {selTf}…</div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              key={`${sel}-${selTf}-${bust}-${chartSignal?.entry ?? 0}`}
              src={api.chartUrl(sel, selTf, bust, chartSignal as Signal | undefined)}
              alt={`${sel} ${selTf} chart`}
              className="w-full rounded-xl border border-line bg-surface min-h-[200px]"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
                setAnalysisErr(`Chart failed to load for ${sel} ${selTf}. Start backend: python -m src.webapp.app`);
              }}
            />
          )
        ) : (
          <TradingViewChart pair={sel} tf={selTf} />
        )}
        {chartSignal && (
          <p className="text-sub text-[11px] mt-2">
            Showing signal overlay from link — entry {fmtPrice(chartSignal.entry!)} · SL {fmtPrice(chartSignal.stop!)} · TP {fmtPrice(chartSignal.target!)}
          </p>
        )}
      </Section>

      {loading && !a && (
        <p className="text-sub text-sm">Loading POI analysis panels…</p>
      )}

      {a && (
        <>
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

"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Config, Status, Signal, JournalRow } from "@/lib/types";
import { StatCard, DirBadge, ConfBar, Section } from "@/components/ui";

function price(v: number) {
  if (!isFinite(v)) return "-";
  if (Math.abs(v) >= 1000) return v.toFixed(1);
  if (Math.abs(v) >= 100) return v.toFixed(3);
  return v.toFixed(5);
}
const money = (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function Dashboard() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [st, setSt] = useState<Status | null>(null);
  const [sigs, setSigs] = useState<Signal[]>([]);
  const [journal, setJournal] = useState<JournalRow[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, sg, jr] = await Promise.all([api.status(), api.signals(), api.journal(40)]);
      setSt(s); setSigs(sg.signals || []); setJournal(jr.rows || []); setErr(null);
    } catch (e: any) {
      setErr(`Can't reach API at ${api.base}. Is the Python backend running?`);
    }
  }, []);

  useEffect(() => {
    api.config().then(setCfg).catch(() => {});
    refresh();
    const t = setInterval(refresh, 15000); // live poll
    return () => clearInterval(t);
  }, [refresh]);

  const runTick = async (rf: boolean) => {
    setBusy(rf ? "refresh" : "tick");
    try { await api.tick(rf); await refresh(); }
    catch { setErr("Tick failed — check the backend logs."); }
    finally { setBusy(null); }
  };

  const tr = st?.track_record;
  const be = cfg?.breakeven ?? st?.breakeven ?? 0.333;
  const navUp = tr ? tr.total_r >= 0 : true;

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-5 sm:py-8">
      {/* header */}
      <header className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold bg-gradient-to-r from-accent to-up bg-clip-text text-transparent">
            MSNR Assistant
          </h1>
          <p className="text-muted text-xs sm:text-sm mt-0.5">
            Malaysian SNR + Smart Money · self-learning signals
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {cfg && <span className="px-2.5 py-1 rounded-full bg-panel2 border border-line">{cfg.tf}/{cfg.bias_tf} · {cfg.target_r}R</span>}
          {cfg && <span className="px-2.5 py-1 rounded-full bg-panel2 border border-line">{cfg.broker}</span>}
          {cfg && <span className={`px-2.5 py-1 rounded-full border ${cfg.telegram ? "border-up/40 text-up" : "border-line text-muted"}`}>
            {cfg.telegram ? "telegram on" : "telegram off"}</span>}
          <span className="flex items-center gap-1 text-muted"><span className="w-2 h-2 rounded-full bg-up animate-pulse" />live</span>
        </div>
      </header>

      {err && <div className="mb-4 p-3 rounded-lg bg-down/10 border border-down/30 text-down text-sm">{err}</div>}

      {/* stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
        <StatCard label="Account NAV" value={st ? money(st.nav) : "—"} sub={cfg?.broker} />
        <StatCard label="Total R" value={tr ? `${tr.total_r >= 0 ? "+" : ""}${tr.total_r.toFixed(1)}R` : "—"} tone={navUp ? "up" : "down"} sub={`${tr?.resolved ?? 0} resolved`} />
        <StatCard label="Win rate" value={tr ? `${(tr.win_rate * 100).toFixed(0)}%` : "—"} sub={`breakeven ${(be * 100).toFixed(0)}%`} tone={tr && tr.win_rate >= be ? "up" : "neutral"} />
        <StatCard label="Expectancy" value={tr ? `${tr.expectancy_r >= 0 ? "+" : ""}${tr.expectancy_r.toFixed(2)}R` : "—"} tone={tr && tr.expectancy_r >= 0 ? "up" : "down"} sub="per trade" />
        <StatCard label="Learned from" value={st ? String(st.n_updates) : "—"} sub="live trades" />
      </div>

      {/* actions */}
      <div className="flex flex-col sm:flex-row gap-2 mb-6">
        <button onClick={() => runTick(false)} disabled={!!busy}
          className="flex-1 sm:flex-none px-5 py-2.5 rounded-lg bg-accent text-white font-medium disabled:opacity-50">
          {busy === "tick" ? "Running…" : "Run tick"}
        </button>
        <button onClick={() => runTick(true)} disabled={!!busy}
          className="flex-1 sm:flex-none px-5 py-2.5 rounded-lg bg-panel2 border border-line text-white font-medium disabled:opacity-50">
          {busy === "refresh" ? "Refreshing data…" : "Refresh data + tick"}
        </button>
        <span className="text-muted text-xs self-center sm:ml-auto">updated {st?.when || "—"}</span>
      </div>

      {/* signals */}
      <div className="mb-4">
        <Section title="Live signals" right={<span className="text-muted text-xs">{sigs.length} found</span>}>
          {sigs.length === 0 ? (
            <p className="text-muted text-sm py-3">No fresh setups on the latest bars.</p>
          ) : (
            <div className="scroll-x">
              <table className="w-full text-sm min-w-[640px]">
                <thead><tr className="text-muted text-xs text-left">
                  <th className="py-2 pr-3">Pair</th><th className="pr-3">Dir</th><th className="pr-3">Entry</th>
                  <th className="pr-3">Stop</th><th className="pr-3">Target</th><th className="pr-3">R:R</th>
                  <th className="pr-3 w-40">Confidence</th><th className="pr-3">Size</th><th></th>
                </tr></thead>
                <tbody>
                  {sigs.map((s, i) => {
                    const take = s.conf >= be && s.size > 0;
                    return (
                      <tr key={i} className="border-t border-line/60">
                        <td className="py-2.5 pr-3 font-semibold">{s.pair}</td>
                        <td className="pr-3"><DirBadge dir={s.direction} /></td>
                        <td className="pr-3 font-mono">{price(s.entry)}</td>
                        <td className="pr-3 font-mono text-down">{price(s.stop)}</td>
                        <td className="pr-3 font-mono text-up">{price(s.target)}</td>
                        <td className="pr-3">1:{cfg?.target_r ?? 2}</td>
                        <td className="pr-3"><ConfBar p={s.conf} breakeven={be} /></td>
                        <td className="pr-3 font-mono">{s.size.toFixed(2)}x</td>
                        <td className="pr-3">
                          <span className={`text-xs font-semibold ${take ? "text-up" : "text-muted"}`}>
                            {take ? "TAKE" : "watch"}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      </div>

      {/* positions + activity */}
      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Open positions" right={<span className="text-muted text-xs">{st?.open_positions.length ?? 0}</span>}>
          {(st?.open_positions.length ?? 0) === 0 ? (
            <p className="text-muted text-sm py-3">No open positions.</p>
          ) : (
            <div className="scroll-x">
              <table className="w-full text-sm min-w-[420px]">
                <thead><tr className="text-muted text-xs text-left"><th className="py-2 pr-3">Pair</th><th className="pr-3">Dir</th><th className="pr-3">Entry</th><th className="pr-3">Stop</th><th className="pr-3">Target</th><th>Size</th></tr></thead>
                <tbody>
                  {st!.open_positions.map((p, i) => (
                    <tr key={i} className="border-t border-line/60">
                      <td className="py-2.5 pr-3 font-semibold">{p.pair}</td>
                      <td className="pr-3"><DirBadge dir={p.direction} /></td>
                      <td className="pr-3 font-mono">{price(p.entry)}</td>
                      <td className="pr-3 font-mono text-down">{price(p.stop)}</td>
                      <td className="pr-3 font-mono text-up">{price(p.target)}</td>
                      <td className="font-mono">{p.size.toFixed(2)}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title="Recent activity" right={<span className="text-muted text-xs">journal</span>}>
          {journal.length === 0 ? (
            <p className="text-muted text-sm py-3">Nothing logged yet — run a tick.</p>
          ) : (
            <ul className="divide-y divide-line/60 max-h-[360px] overflow-y-auto">
              {journal.map((r, i) => {
                const close = r.event === "CLOSE";
                const win = r.outcome === "win";
                return (
                  <li key={i} className="py-2.5 flex items-center justify-between gap-2 text-sm">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${close ? "bg-panel2" : "bg-accent/15 text-accent"}`}>{r.event}</span>
                      <span className="font-semibold">{r.pair}</span>
                      <DirBadge dir={r.direction} />
                    </div>
                    <div className="text-right">
                      {close ? (
                        <span className={win ? "text-up" : "text-down"}>
                          {win ? "WIN" : "LOSS"} {Number(r.r).toFixed(2)}R
                        </span>
                      ) : (
                        <span className="text-muted font-mono">@ {price(Number(r.entry))}</span>
                      )}
                      <div className="text-muted text-[11px]">{(r.ts || "").replace("T", " ").slice(0, 16)}</div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Section>
      </div>

      <footer className="text-muted text-xs mt-8 leading-relaxed">
        Decision-support only — not financial advice. The model's edge is small and unproven; paper-trade and
        verify before risking real capital. Pairs: {cfg?.pairs.join(", ")}.
      </footer>
    </main>
  );
}

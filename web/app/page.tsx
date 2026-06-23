"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useLive, fmtPrice } from "@/lib/useLive";
import type { Config, Status, Signal, JournalRow, PairOverview } from "@/lib/types";
import { StatCard, DirBadge, Section } from "@/components/ui";

const money = (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function Overview() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [st, setSt] = useState<Status | null>(null);
  const [sigs, setSigs] = useState<Signal[]>([]);
  const [ov, setOv] = useState<PairOverview[]>([]);
  const [jr, setJr] = useState<JournalRow[]>([]);

  const load = useCallback(async () => {
    const [c, s, sg, o, j] = await Promise.all([
      api.config().catch(() => null), api.status().catch(() => null),
      api.signals().catch(() => ({ signals: [] })), api.overview().catch(() => ({ overview: [] })),
      api.journal(12).catch(() => ({ rows: [] })),
    ]);
    if (c) setCfg(c); if (s) setSt(s);
    setSigs(sg.signals || []); setOv(o.overview || []); setJr(j.rows || []);
  }, []);
  useLive(load);

  const tr = st?.track_record;
  const be = cfg?.breakeven ?? 0.333;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Overview</h1>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <StatCard label="Account NAV" value={st ? money(st.nav) : "—"} sub={cfg?.broker} />
        <StatCard label="Total R" value={tr ? `${tr.total_r >= 0 ? "+" : ""}${tr.total_r.toFixed(1)}R` : "—"} tone={tr && tr.total_r >= 0 ? "up" : "down"} sub={`${tr?.resolved ?? 0} resolved`} />
        <StatCard label="Win rate" value={tr ? `${(tr.win_rate * 100).toFixed(0)}%` : "—"} sub={`breakeven ${(be * 100).toFixed(0)}%`} tone={tr && tr.win_rate >= be ? "up" : "neutral"} />
        <StatCard label="Expectancy" value={tr ? `${tr.expectancy_r >= 0 ? "+" : ""}${tr.expectancy_r.toFixed(2)}R` : "—"} tone={tr && tr.expectancy_r >= 0 ? "up" : "down"} sub="per trade" />
        <StatCard label="Learned from" value={st ? String(st.n_updates) : "—"} sub="live trades" />
      </div>

      <Section title="Pairs" right={<Link href="/pairs" className="text-brand text-xs font-medium">open pairs →</Link>}>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {ov.length === 0 && <p className="text-sub text-sm">No data yet — run a tick.</p>}
          {ov.map((o) => (
            <Link key={o.pair} href={`/pairs?p=${o.pair}`}
              className="flex items-center justify-between p-3 rounded-xl border border-line bg-surface hover:border-brand/40 transition">
              <div>
                <div className="font-semibold text-sm">{o.pair}</div>
                <div className="text-sub text-xs font-mono">{fmtPrice(o.price)}</div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <DirBadge dir={o.bias} />
                {o.signal && <span className="text-[10px] text-brand font-semibold">● signal</span>}
              </div>
            </Link>
          ))}
        </div>
      </Section>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Live signals" right={<Link href="/signals" className="text-brand text-xs font-medium">all →</Link>}>
          {sigs.length === 0 ? <p className="text-sub text-sm py-2">No fresh setups (MSNR is low-frequency).</p> : (
            <ul className="space-y-2">
              {sigs.slice(0, 6).map((s, i) => (
                <li key={i} className="flex items-center justify-between p-2.5 rounded-lg border border-line">
                  <div className="flex items-center gap-2"><span className="font-semibold text-sm">{s.pair}</span><DirBadge dir={s.direction} /></div>
                  <div className="text-xs text-sub">conf <span className={`font-semibold ${s.conf >= be ? "text-up" : ""}`}>{(s.conf * 100).toFixed(0)}%</span> · {s.size.toFixed(2)}x</div>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Recent activity" right={<span className="text-sub text-xs">journal</span>}>
          {jr.length === 0 ? <p className="text-sub text-sm py-2">Nothing logged yet.</p> : (
            <ul className="divide-y divide-line">
              {jr.map((r, i) => {
                const close = r.event === "CLOSE", win = r.outcome === "win";
                return (
                  <li key={i} className="py-2 flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2"><span className={`text-[10px] px-1.5 py-0.5 rounded ${close ? "bg-line text-sub" : "bg-brand/10 text-brand"}`}>{r.event}</span><span className="font-semibold">{r.pair}</span></span>
                    {close ? <span className={`font-semibold ${win ? "text-up" : "text-down"}`}>{win ? "WIN" : "LOSS"} {Number(r.r).toFixed(2)}R</span> : <span className="text-sub font-mono">@ {fmtPrice(Number(r.entry))}</span>}
                  </li>
                );
              })}
            </ul>
          )}
        </Section>
      </div>
    </div>
  );
}

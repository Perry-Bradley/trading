"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useLive, fmtPrice } from "@/lib/useLive";
import type { Config, Signal } from "@/lib/types";
import { DirBadge, ConfBar, Section } from "@/components/ui";
import { LiveChart } from "@/components/LiveChart";

function StatusBadge({ s }: { s: Signal }) {
  const map: Record<string, { t: string; c: string }> = {
    live: { t: "● LIVE", c: "bg-up/15 text-up" },
    open: { t: "OPEN", c: "bg-brand/10 text-brand" },
    won: { t: "WON ✓", c: "bg-up/15 text-up" },
    lost: { t: "LOST ✕", c: "bg-down/15 text-down" },
  };
  const m = map[s.status || "open"] || map.open;
  return <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${m.c}`}>{m.t}</span>;
}

function SignalCard({
  s, open, onToggle, be, bust,
}: {
  s: Signal; open: boolean; onToggle: () => void; be: number; bust: number;
}) {
  const take = s.status === "live" && s.conf >= be && s.size > 0;
  return (
    <div className="bg-surface border border-line rounded-2xl p-4 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="text-lg font-bold">{s.pair}</span>
          <DirBadge dir={s.direction} />
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-brand/10 text-brand">{s.tf || "H4"}</span>
          <StatusBadge s={s} />
          <span className="text-sub text-xs">
            1:{s.rr?.toFixed(2) ?? 3}{s.time ? ` · ${s.time}` : ""}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-40"><ConfBar p={s.conf} breakeven={be} /></div>
          {s.status === "live" && (
            <span className={`text-xs font-bold px-2.5 py-1 rounded-lg ${take ? "bg-up/10 text-up" : "bg-line text-sub"}`}>
              {take ? "TAKE" : "WATCH"}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="rounded-lg bg-canvas border border-line p-2.5">
          <div className="text-[11px] text-sub">Entry</div>
          <div className="font-mono font-semibold">{fmtPrice(s.entry)}</div>
        </div>
        <div className="rounded-lg bg-canvas border border-line p-2.5">
          <div className="text-[11px] text-sub">Stop loss</div>
          <div className="font-mono font-semibold text-down">{fmtPrice(s.stop)}</div>
        </div>
        <div className="rounded-lg bg-canvas border border-line p-2.5">
          <div className="text-[11px] text-sub">Take profit</div>
          <div className="font-mono font-semibold text-up">{fmtPrice(s.target)}</div>
        </div>
      </div>

      {s.why && <p className="text-sm text-ink/80 mb-2">{s.why}</p>}
      {s.confluences && s.confluences.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {s.confluences.map((c, j) => (
            <span key={j} className="text-[11px] px-2 py-0.5 rounded-full bg-brand/10 text-brand">{c}</span>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onToggle}
        className="text-brand text-sm font-medium hover:underline mb-2"
      >
        {open ? "Hide chart ▲" : "Show annotated chart ▼"}
      </button>

      {open && (
        <Section title="Live chart — entry/SL/TP + POI annotations" right={
          <div className="flex items-center gap-3">
            <a href={api.signalChartUrl(s, bust)} target="_blank" rel="noreferrer" className="text-sub text-xs hover:underline">static PNG ↗</a>
            <a
              href={`/pairs?p=${s.pair}&tf=${s.tf || "H4"}&entry=${s.entry}&stop=${s.stop}&target=${s.target}&dir=${s.direction}${s.bar_idx != null ? `&bar=${s.bar_idx}` : ""}${s.zone_top != null ? `&zt=${s.zone_top}` : ""}${s.zone_bottom != null ? `&zb=${s.zone_bottom}` : ""}${s.zone_kind ? `&zk=${s.zone_kind}` : ""}`}
              className="text-brand text-xs hover:underline"
            >
              open on Pairs page →
            </a>
          </div>
        }>
          <LiveChart pair={s.pair} tf={s.tf || "H4"} signal={s} annotate />
          <p className="text-sub text-[11px] mt-2">
            Bold lines = Entry/SL/TP · yellow dashed = tapped POI · green/red dashed = OB/BB/SNR/FVG ·
            markers = CHoCH/BOS · sweeps · QM. {s.status === "won" && "This prediction hit target ✓"}
            {s.status === "lost" && "This prediction hit stop ✕"}
          </p>
        </Section>
      )}
    </div>
  );
}

export default function Signals() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [recent, setRecent] = useState<Signal[]>([]);
  const [seed, setSeed] = useState("idle");
  const [bust, setBust] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [c, r] = await Promise.all([
      api.config().catch(() => null),
      api.recentSignals().catch(() => ({ signals: [], seed_state: "" })),
    ]);
    if (c) setCfg(c);
    setRecent(r.signals || []);
    setSeed(r.seed_state || "ready");
    setBust(Date.now());
  }, []);
  useLive(load, 15000);

  const be = cfg?.breakeven ?? 0.333;
  const active = recent.filter((s) => s.status === "live" || s.status === "open");
  const resolved = recent.filter((s) => s.status === "won" || s.status === "lost");
  const wins = resolved.filter((s) => s.status === "won").length;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h1 className="text-xl font-bold">Signals — predictions & outcomes</h1>
        <span className="text-sub text-sm">{active.length} active · {resolved.length} resolved</span>
      </div>
      <p className="text-sub text-sm">
        A signal is a prediction (entry · SL · TP with its “why”). <b className="text-ink">Active</b> = still
        running; <b className="text-ink">resolved</b> = already hit target or stop — that’s what the journal records.
        {seed === "warming" && " (Still warming up — give it a moment.)"}
      </p>

      <Section title={`Active now (${active.length})`}>
        {active.length === 0 ? (
          <p className="text-sub text-sm py-2">
            No running predictions this moment — MSNR is low-frequency. Resolved ones are below, and the paper
            engine keeps testing every setup in the background.
          </p>
        ) : (
          <div className="space-y-4">
            {active.map((s, i) => {
              const id = `a-${s.pair}-${s.tf}-${s.time}-${i}`;
              return <SignalCard key={id} s={s} open={openId === id} onToggle={() => setOpenId(openId === id ? null : id)} be={be} bust={bust} />;
            })}
          </div>
        )}
      </Section>

      {resolved.length > 0 && (
        <Section title={`Recently resolved (${resolved.length}) — ${wins} won / ${resolved.length - wins} lost`}>
          <div className="space-y-4">
            {resolved.map((s, i) => {
              const id = `r-${s.pair}-${s.tf}-${s.time}-${i}`;
              return <SignalCard key={id} s={s} open={openId === id} onToggle={() => setOpenId(openId === id ? null : id)} be={be} bust={bust} />;
            })}
          </div>
        </Section>
      )}
    </div>
  );
}

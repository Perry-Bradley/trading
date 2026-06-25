"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useLive, fmtPrice } from "@/lib/useLive";
import type { Config, Signal } from "@/lib/types";
import { DirBadge, ConfBar, Section } from "@/components/ui";

const HRS: Record<string, number> = { D1: 24, H4: 4, H1: 1, M30: 0.5 };

function freshness(s: Signal): { label: string; live: boolean } {
  const age = s.age_bars ?? 99;
  if (age <= 1) return { label: "FRESH NOW", live: true };
  const hrs = age * (HRS[s.tf || "H4"] ?? 4);
  if (hrs < 24) return { label: `${Math.round(hrs)}h ago`, live: false };
  return { label: `${Math.round(hrs / 24)}d ago`, live: false };
}

export default function Signals() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [sigs, setSigs] = useState<Signal[]>([]);
  const [seed, setSeed] = useState("idle");
  const [bust, setBust] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(0);

  const load = useCallback(async () => {
    const [c, sg] = await Promise.all([
      api.config().catch(() => null),
      api.signals().catch(() => ({ signals: [], seed_state: "" })),
    ]);
    if (c) setCfg(c);
    setSigs(sg.signals || []);
    setSeed(sg.seed_state || "ready");
    setBust(Date.now());
  }, []);
  useLive(load, 15000);

  const be = cfg?.breakeven ?? 0.333;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h1 className="text-xl font-bold">Live signals</h1>
        <span className="text-sub text-sm">{sigs.length} setup{sigs.length === 1 ? "" : "s"} now</span>
      </div>
      <p className="text-sub text-sm">
        Setups from the same data the chart uses — SNR tap + rejection in HTF bias direction.
        Each chart is zoomed to the signal bar with POI labels (OB, BB, QM, BSL/SSL, FVG) and
        confluence reasons drawn on it. <b className="text-up">TAKE</b> = confidence above
        {(be * 100).toFixed(0)}% breakeven for {cfg?.target_r ?? 3}R.
      </p>

      {sigs.length === 0 ? (
        <Section title="No fresh setups">
          <p className="text-sub text-sm py-2">
            Nothing is at a valid level right now. MSNR waits for structure + fresh level + rejection.
            {seed === "warming" && " (Still warming up.)"}
          </p>
        </Section>
      ) : (
        <div className="space-y-4">
          {sigs.map((s, i) => {
            const take = s.conf >= be && s.size > 0;
            const open = expanded === i;
            return (
              <div key={`${s.pair}-${s.tf}-${s.time}-${i}`} className="bg-surface border border-line rounded-2xl p-4 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="text-lg font-bold">{s.pair}</span>
                    <DirBadge dir={s.direction} />
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-brand/10 text-brand">{s.tf || "H4"}</span>
                    {s.tf_aligned && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-up/10 text-up">
                        ✓ TF ALIGNED{s.aligned_tf ? ` (${s.aligned_tf})` : ""}
                      </span>
                    )}
                    {s.features?.session_score === 1 && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-400">SESSION</span>
                    )}
                    {(() => {
                      const f = freshness(s);
                      return (
                        <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${f.live ? "bg-up/10 text-up" : "bg-line text-sub"}`}>
                          {f.live ? "● " : ""}{f.label}
                        </span>
                      );
                    })()}
                    <span className="text-sub text-xs">
                      1:{s.rr?.toFixed(2) ?? cfg?.target_r ?? 3}{s.time ? ` · ${s.time}` : ""}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-40"><ConfBar p={s.conf} breakeven={be} /></div>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-lg ${take ? "bg-up/10 text-up" : "bg-line text-sub"}`}>
                      {take ? "TAKE" : "WATCH"}
                    </span>
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
                  onClick={() => setExpanded(open ? null : i)}
                  className="text-brand text-sm font-medium hover:underline mb-2"
                >
                  {open ? "Hide chart ▲" : "Show annotated chart ▼"}
                </button>

                {open && (
                  <Section title="Signal chart — zoomed to setup" right={
                    <a
                      href={`/pairs?p=${s.pair}&tf=${s.tf || "H4"}&entry=${s.entry}&stop=${s.stop}&target=${s.target}&dir=${s.direction}${s.bar_idx != null ? `&bar=${s.bar_idx}` : ""}${s.zone_top != null ? `&zt=${s.zone_top}` : ""}${s.zone_bottom != null ? `&zb=${s.zone_bottom}` : ""}${s.zone_kind ? `&zk=${s.zone_kind}` : ""}${s.confluences?.length ? `&notes=${encodeURIComponent(s.confluences.slice(0, 7).join("|"))}` : ""}`}
                      className="text-brand text-xs hover:underline"
                    >
                      open on Pairs page →
                    </a>
                  }>
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      key={api.signalChartUrl(s, bust)}
                      src={api.signalChartUrl(s, bust)}
                      alt={`${s.pair} ${s.tf} signal chart`}
                      className="w-full rounded-xl border border-line bg-canvas"
                    />
                    <p className="text-sub text-[11px] mt-2">
                      POI legend: OB = Order Block · BB = Breaker · QM = Quasimodo · BSL/SSL = Liquidity sweep · FVG = Fair Value Gap
                    </p>
                  </Section>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

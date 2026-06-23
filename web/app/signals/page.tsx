"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useLive, fmtPrice } from "@/lib/useLive";
import type { Config, Signal } from "@/lib/types";
import { DirBadge, ConfBar, Section } from "@/components/ui";

export default function Signals() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [sigs, setSigs] = useState<(Signal & { why?: string; confluences?: string[] })[]>([]);
  const [seed, setSeed] = useState("idle");

  const load = useCallback(async () => {
    const [c, sg] = await Promise.all([api.config().catch(() => null), api.signals().catch(() => ({ signals: [], seed_state: "" }))]);
    if (c) setCfg(c);
    setSigs(sg.signals || []); setSeed(sg.seed_state || "ready");
  }, []);
  useLive(load);

  const be = cfg?.breakeven ?? 0.333;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h1 className="text-xl font-bold">Live signals</h1>
        <span className="text-sub text-sm">{sigs.length} setup{sigs.length === 1 ? "" : "s"} now</span>
      </div>
      <p className="text-sub text-sm">
        Each setup is a fresh MSNR level tapped with a rejection candle, in the direction of higher-timeframe
        structure, scored by the self-learning model. <b className="text-up">TAKE</b> = model confidence above
        the {(be * 100).toFixed(0)}% breakeven for {cfg?.target_r ?? 2}R; otherwise it&apos;s a watch.
      </p>

      {sigs.length === 0 ? (
        <Section title="No fresh setups">
          <p className="text-sub text-sm py-2">
            Nothing is at a valid level right now. MSNR is precision-not-frequency — the assistant waits and only
            flags when structure, a fresh level, and a rejection line up. {seed === "warming" && "(Still warming up.)"}
          </p>
        </Section>
      ) : (
        <div className="space-y-3">
          {sigs.map((s, i) => {
            const take = s.conf >= be && s.size > 0;
            return (
              <div key={i} className="bg-surface border border-line rounded-2xl p-4 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="text-lg font-bold">{s.pair}</span>
                    <DirBadge dir={s.direction} />
                    <span className="text-sub text-xs">{s.tf || cfg?.tf} · 1:{cfg?.target_r ?? 2}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="w-40"><ConfBar p={s.conf} breakeven={be} /></div>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-lg ${take ? "bg-up/10 text-up" : "bg-line text-sub"}`}>
                      {take ? "TAKE" : "WATCH"} · {s.size.toFixed(2)}x
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="rounded-lg bg-canvas border border-line p-2.5">
                    <div className="text-[11px] text-sub">Entry</div><div className="font-mono font-semibold">{fmtPrice(s.entry)}</div></div>
                  <div className="rounded-lg bg-canvas border border-line p-2.5">
                    <div className="text-[11px] text-sub">Stop loss</div><div className="font-mono font-semibold text-down">{fmtPrice(s.stop)}</div></div>
                  <div className="rounded-lg bg-canvas border border-line p-2.5">
                    <div className="text-[11px] text-sub">Take profit</div><div className="font-mono font-semibold text-up">{fmtPrice(s.target)}</div></div>
                </div>
                {s.why && <p className="text-sm text-ink/80 mb-2">{s.why}</p>}
                {s.confluences && s.confluences.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {s.confluences.map((c, j) => (
                      <span key={j} className="text-[11px] px-2 py-0.5 rounded-full bg-brand/10 text-brand">{c}</span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

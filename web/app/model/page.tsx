"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useLive } from "@/lib/useLive";
import type { ModelInfo } from "@/lib/types";
import { StatCard, Section } from "@/components/ui";

export default function ModelPage() {
  const [m, setM] = useState<ModelInfo | null>(null);
  const load = useCallback(async () => { try { setM(await api.model()); } catch { /* */ } }, []);
  useLive(load, 20000);

  const maxW = m ? Math.max(...m.coef.map((c) => Math.abs(c.weight)), 0.001) : 1;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Model — the self-learning core</h1>
      <p className="text-sub text-sm">
        A contextual-bandit (online logistic model) that scores each setup&apos;s win probability, sizes positions by
        confidence, and <b>updates itself after every closed trade</b> (`partial_fit`). It adapts — it doesn&apos;t
        guarantee an edge. The honest signal strength is the cross-validated AUC below (0.5 = no edge).
      </p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="CV AUC" value={m?.cv_auc != null ? m.cv_auc.toFixed(3) : "—"} sub="0.5 = no edge" tone={m && m.cv_auc && m.cv_auc > 0.55 ? "up" : "neutral"} />
        <StatCard label="Target R" value={m ? `${m.target_r}R` : "—"} sub={`breakeven ${m ? (m.breakeven * 100).toFixed(0) : "—"}%`} />
        <StatCard label="Learned from" value={m ? String(m.n_updates) : "—"} sub="live trades" />
        <StatCard label="Features" value={m ? String(m.features.length) : "—"} sub="causal inputs" />
      </div>

      <Section title="What the model leans on" right={<span className="text-sub text-xs">standardised weights · + favours a win</span>}>
        {!m || m.coef.length === 0 ? <p className="text-sub text-sm py-2">Warming up…</p> : (
          <ul className="space-y-2">
            {m.coef.map((c) => (
              <li key={c.feature} className="flex items-center gap-3">
                <span className="w-36 shrink-0 text-sm">{c.feature}</span>
                <div className="flex-1 h-3 rounded-full bg-line relative overflow-hidden">
                  <div className={`absolute top-0 h-full ${c.weight >= 0 ? "bg-up left-1/2" : "bg-down right-1/2"}`}
                    style={{ width: `${(Math.abs(c.weight) / maxW) * 50}%` }} />
                  <div className="absolute left-1/2 top-0 h-full w-px bg-sub/40" />
                </div>
                <span className={`w-16 text-right text-xs font-mono ${c.weight >= 0 ? "text-up" : "text-down"}`}>{c.weight >= 0 ? "+" : ""}{c.weight.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="How it learns (RL loop)">
        <ol className="text-sm text-ink/80 space-y-1.5 list-decimal pl-5">
          <li>Each tick scans all pairs for fresh MSNR setups and scores them with the current model.</li>
          <li>Confident setups (above breakeven) open paper trades, sized by edge.</li>
          <li>When a trade hits its stop or target, the real outcome is fed back via <code className="bg-canvas px-1 rounded">partial_fit</code>.</li>
          <li>The updated model is saved and used for the next tick — so it keeps adapting to what actually works.</li>
        </ol>
      </Section>
    </div>
  );
}

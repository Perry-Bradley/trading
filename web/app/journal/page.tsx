"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useLive, fmtPrice } from "@/lib/useLive";
import type { JournalRow, Status } from "@/lib/types";
import { DirBadge, Section } from "@/components/ui";

export default function Journal() {
  const [jr, setJr] = useState<JournalRow[]>([]);
  const [st, setSt] = useState<Status | null>(null);

  const load = useCallback(async () => {
    const [j, s] = await Promise.all([
      api.journal(100).catch(() => ({ rows: [] })),
      api.status().catch(() => null)
    ]);
    setJr(j.rows || []);
    if (s) setSt(s);
  }, []);
  useLive(load);

  const tr = st?.track_record;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h1 className="text-xl font-bold">Trading Journal</h1>
      </div>
      
      {tr && (
        <p className="text-sub text-sm">
          Track record: <span className="font-semibold text-ink">{tr.wins}W - {tr.resolved - tr.wins}L</span> 
          {" "}({((tr.wins / tr.resolved) * 100).toFixed(1)}%) | 
          Net: <span className={`font-semibold ${tr.total_r >= 0 ? "text-up" : "text-down"}`}>
            {tr.total_r >= 0 ? "+" : ""}{tr.total_r.toFixed(2)}R
          </span>
        </p>
      )}

      <Section title="Recorded trades">
        {jr.length === 0 ? (
          <p className="text-sub text-sm py-2">Nothing logged yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead>
                <tr className="text-sub border-b border-line">
                  <th className="font-semibold py-2">Time</th>
                  <th className="font-semibold py-2">Pair</th>
                  <th className="font-semibold py-2">Dir</th>
                  <th className="font-semibold py-2">Outcome</th>
                  <th className="font-semibold py-2">R</th>
                  <th className="font-semibold py-2">P&L</th>
                  <th className="font-semibold py-2">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {jr.map((r, i) => {
                  const close = r.event === "CLOSE";
                  const win = r.outcome === "win";
                  return (
                    <tr key={i} className="group hover:bg-surface/50 transition">
                      <td className="py-2.5 font-mono text-[11px] text-sub">{(r as any).exit_time?.substring(0,16) || r.ts.substring(0,16)}</td>
                      <td className="py-2.5 font-semibold">{r.pair}</td>
                      <td className="py-2.5"><DirBadge dir={r.direction} /></td>
                      <td className="py-2.5">
                        {close ? (
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${win ? "bg-up/10 text-up" : "bg-down/10 text-down"}`}>
                            {r.outcome.toUpperCase()}
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-brand/10 text-brand">OPEN</span>
                        )}
                      </td>
                      <td className={`py-2.5 font-semibold ${close ? (win ? "text-up" : "text-down") : "text-sub"}`}>
                        {close ? `${Number(r.r).toFixed(2)}R` : "—"}
                      </td>
                      <td className={`py-2.5 font-mono ${close ? (Number(r.pnl) >= 0 ? "text-up" : "text-down") : "text-sub"}`}>
                        {close ? `${Number(r.pnl) >= 0 ? "+" : ""}${Number(r.pnl).toFixed(2)}` : "—"}
                      </td>
                      <td className="py-2.5 text-[11px] text-sub max-w-[200px] truncate" title={(r as any).why}>
                        {(r as any).why || "—"}
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
  );
}

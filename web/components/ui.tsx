import React from "react";

export function StatCard({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: "up" | "down" | "neutral";
}) {
  const color = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-white";
  return (
    <div className="bg-panel border border-line rounded-xl p-4 flex flex-col gap-1">
      <div className="text-muted text-xs uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-muted text-xs">{sub}</div>}
    </div>
  );
}

export function DirBadge({ dir }: { dir: string }) {
  const long = dir === "long";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
      long ? "bg-up/15 text-up" : "bg-down/15 text-down"
    }`}>{dir.toUpperCase()}</span>
  );
}

export function ConfBar({ p, breakeven }: { p: number; breakeven: number }) {
  const pct = Math.max(0, Math.min(100, p * 100));
  const good = p >= breakeven;
  return (
    <div className="flex items-center gap-2 min-w-[110px]">
      <div className="flex-1 h-1.5 rounded-full bg-line overflow-hidden">
        <div className={`h-full ${good ? "bg-up" : "bg-muted"}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs tabular-nums ${good ? "text-up" : "text-muted"}`}>{pct.toFixed(0)}%</span>
    </div>
  );
}

export function Section({ title, children, right }: {
  title: string; children: React.ReactNode; right?: React.ReactNode;
}) {
  return (
    <section className="bg-panel border border-line rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-white">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

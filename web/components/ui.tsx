import React from "react";

export function StatCard({ label, value, sub, tone }: {
  label: string; value: string; sub?: string; tone?: "up" | "down" | "neutral";
}) {
  const color = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink";
  return (
    <div className="bg-surface border border-line rounded-2xl p-4 shadow-card">
      <div className="text-sub text-[11px] font-medium uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${color}`}>{value}</div>
      {sub && <div className="text-sub text-xs mt-0.5">{sub}</div>}
    </div>
  );
}

export function DirBadge({ dir }: { dir: string }) {
  if (dir === "flat") return <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-line text-sub">FLAT</span>;
  const long = dir === "long";
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
      long ? "bg-up/10 text-up" : "bg-down/10 text-down"
    }`}>{long ? "LONG" : "SHORT"}</span>
  );
}

export function ConfBar({ p, breakeven }: { p: number; breakeven: number }) {
  const pct = Math.max(0, Math.min(100, p * 100));
  const good = p >= breakeven;
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-2 rounded-full bg-line overflow-hidden">
        <div className={`h-full rounded-full ${good ? "bg-up" : "bg-sub"}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-semibold tabular-nums ${good ? "text-up" : "text-sub"}`}>{pct.toFixed(0)}%</span>
    </div>
  );
}

export function Section({ title, children, right }: {
  title: string; children: React.ReactNode; right?: React.ReactNode;
}) {
  return (
    <section className="bg-surface border border-line rounded-2xl p-4 sm:p-5 shadow-card">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function Chip({ active, children, onClick, dot }: {
  active?: boolean; children: React.ReactNode; onClick?: () => void; dot?: "up" | "down" | null;
}) {
  return (
    <button onClick={onClick}
      className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm transition
        ${active ? "border-brand bg-brand/5 text-brand font-semibold" : "border-line bg-surface text-ink hover:border-brand/40"}`}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot === "up" ? "bg-up" : "bg-down"}`} />}
      {children}
    </button>
  );
}

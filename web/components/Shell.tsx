"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Config } from "@/lib/types";

const NAV = [
  { href: "/", label: "Overview", icon: "▦" },
  { href: "/signals", label: "Signals", icon: "◎" },
  { href: "/journal", label: "Journal", icon: "📓" },
  { href: "/pairs", label: "Pairs", icon: "⇄" },
  { href: "/performance", label: "Performance", icon: "📈" },
  { href: "/model", label: "Model", icon: "✦" },
  { href: "/data", label: "Data pipeline", icon: "⛁" },
];

export function emitRefresh() {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("msnr:refresh"));
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [cfg, setCfg] = useState<Config | null>(null);
  const [seed, setSeed] = useState("idle");
  const [when, setWhen] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);

  const [apiErr, setApiErr] = useState<string | null>(null);

  const poll = useCallback(async () => {
    try {
      const s = await api.status();
      setSeed(s.seed_state || "ready");
      setWhen(s.when || "");
      setApiErr(null);
    } catch {
      setApiErr("Cannot reach API — set API_URL on this Railway service");
    }
  }, []);

  useEffect(() => {
    api.config().then(setCfg).catch(() => {});
    poll();
    let t: ReturnType<typeof setInterval>;
    const schedule = () => {
      clearInterval(t);
      t = setInterval(poll, when === "never" || !when ? 5000 : 30000);
    };
    schedule();
    return () => clearInterval(t);
  }, [poll, when]);

  const runTick = async (rf: boolean) => {
    setBusy(rf ? "refresh" : "tick");
    try { await api.tick(rf); emitRefresh(); await poll(); }
    catch { /* surfaced by pages */ }
    finally { setBusy(null); }
  };

  const warming = seed === "warming" || seed.startsWith("error");

  const NavLinks = ({ onClick }: { onClick?: () => void }) => (
    <>
      {NAV.map((n) => {
        const active = path === n.href;
        return (
          <Link key={n.href} href={n.href} onClick={onClick}
            className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition shrink-0
              ${active ? "bg-brand/10 text-brand font-semibold" : "text-ink/70 hover:bg-line/60"}`}>
            <span className="text-base leading-none">{n.icon}</span>{n.label}
          </Link>
        );
      })}
    </>
  );

  return (
    <div className="lg:flex min-h-screen">
      {/* sidebar (desktop) */}
      <aside className="hidden lg:flex flex-col w-60 shrink-0 border-r border-line bg-surface lg:sticky lg:top-0 lg:h-screen p-4">
        <div className="flex items-center gap-2.5 px-1 mb-5">
          <div className="w-9 h-9 rounded-xl bg-brand text-white grid place-items-center font-bold shadow-pop">M</div>
          <div>
            <div className="font-bold text-ink leading-tight">MSNR</div>
            <div className="text-[11px] text-sub">trading assistant</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">{<NavLinks />}</nav>
        <div className="mt-auto text-[11px] text-sub leading-relaxed pt-4">
          Decision-support only. Not financial advice. Paper-trade first.
        </div>
      </aside>

      <div className="flex-1 min-w-0">
        {/* topbar */}
        <div className="sticky top-0 z-10 bg-canvas/85 backdrop-blur border-b border-line">
          <div className="px-4 sm:px-6 py-3 flex flex-wrap items-center gap-2">
            <span className="lg:hidden font-bold text-ink mr-1">MSNR</span>
            {cfg && <span className="px-2.5 py-1 rounded-full bg-surface border border-line text-xs text-ink font-medium">{cfg.tf}/{cfg.bias_tf} · {cfg.target_r}R</span>}
            {cfg && <span className="px-2.5 py-1 rounded-full bg-surface border border-line text-xs">{cfg.broker}</span>}
            {cfg && <span className={`px-2.5 py-1 rounded-full text-xs border ${cfg.telegram ? "border-up/40 text-up bg-up/5" : "border-line text-sub"}`}>{cfg.telegram ? "telegram on" : "telegram off"}</span>}
            <span className="hidden sm:flex items-center gap-1 text-xs text-sub">
              <span className={`w-2 h-2 rounded-full ${warming ? "bg-warn" : "bg-up"} animate-pulse`} />
              {warming ? "warming" : "live"}
              {when && !warming && <span className="text-[10px] text-sub/60 ml-1">· {when.split(" ")[1]}</span>}
            </span>
            <div className="ml-auto flex items-center gap-2">
              <button onClick={() => runTick(false)} disabled={!!busy}
                className="px-3.5 py-1.5 rounded-lg bg-brand text-white text-sm font-medium disabled:opacity-50">
                {busy === "tick" ? "…" : "Run tick"}
              </button>
              <button onClick={() => runTick(true)} disabled={!!busy}
                className="hidden sm:block px-3.5 py-1.5 rounded-lg bg-surface border border-line text-ink text-sm font-medium disabled:opacity-50 hover:border-brand/40">
                {busy === "refresh" ? "…" : "Refresh + tick"}
              </button>
            </div>
          </div>
          {/* mobile nav */}
          <nav className="lg:hidden flex gap-1.5 px-4 pb-2.5 overflow-x-auto scroll-x">{<NavLinks />}</nav>
        </div>

        {apiErr && (
          <div className="mx-4 sm:mx-6 mt-4 p-3 rounded-xl bg-down/5 border border-down/30 text-down text-sm">
            {apiErr}. On the <b>web/dashboard</b> Railway service set:{" "}
            <code className="bg-canvas px-1 rounded">API_URL=https://web-production-6447a.up.railway.app</code>
          </div>
        )}

        {warming && !apiErr && (
          <div className="mx-4 sm:mx-6 mt-4 p-3 rounded-xl bg-warn/5 border border-warn/30 text-warn text-sm">
            {seed.startsWith("error")
              ? `Seeding error: ${seed.replace("error:", "").trim()} — press "Refresh + tick".`
              : "Warming up — fetching market data & training the model (~1–2 min on a fresh deploy). Panels fill in automatically."}
          </div>
        )}

        <main className="px-4 sm:px-6 py-4 sm:py-6">{children}</main>
        {when && <div className="px-4 sm:px-6 pb-6 text-[11px] text-sub">last tick: {when}</div>}
      </div>
    </div>
  );
}

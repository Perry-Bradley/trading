"use client";

import { useEffect, useRef, useId } from "react";

const TV_SYMBOL: Record<string, string> = {
  EURUSD: "FX:EURUSD",
  GBPUSD: "FX:GBPUSD",
  AUDUSD: "FX:AUDUSD",
  XAUUSD: "OANDA:XAUUSD",
  BTCUSD: "BINANCE:BTCUSDT",
  V100: "DERIV:V100",
  V25: "DERIV:V25",
};

const TV_INTERVAL: Record<string, string> = {
  H4: "240",
  H1: "60",
  M30: "30",
};

declare global {
  interface Window {
    TradingView?: { widget: new (opts: Record<string, unknown>) => void };
  }
}

export function TradingViewChart({ pair, tf }: { pair: string; tf: string }) {
  const id = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const containerId = `tv_${id}`;
    if (containerRef.current) containerRef.current.id = containerId;

    const mount = () => {
      if (!window.TradingView || !containerRef.current) return;
      containerRef.current.innerHTML = "";
      new window.TradingView.widget({
        autosize: true,
        symbol: TV_SYMBOL[pair] || `FX:${pair}`,
        interval: TV_INTERVAL[tf] || "240",
        timezone: "Etc/UTC",
        theme: "dark",
        style: "1",
        locale: "en",
        enable_publishing: false,
        hide_top_toolbar: false,
        hide_legend: false,
        save_image: false,
        container_id: containerId,
        studies: [],
      });
    };

    if (window.TradingView) {
      mount();
      return;
    }
    const existing = document.querySelector('script[src="https://s3.tradingview.com/tv.js"]');
    if (existing) {
      existing.addEventListener("load", mount);
      return () => existing.removeEventListener("load", mount);
    }
    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = mount;
    document.head.appendChild(script);
    return () => {
      script.onload = null;
    };
  }, [pair, tf, id]);

  return (
    <div className="w-full rounded-xl border border-line overflow-hidden bg-[#131722]">
      <div ref={containerRef} className="h-[520px] w-full" />
      <p className="text-[11px] text-sub px-3 py-2 border-t border-line">
        Live TradingView chart · UTC · updates in real time
      </p>
    </div>
  );
}

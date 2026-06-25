"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type IPriceLine,
  type CandlestickData,
  type SeriesMarker,
  type UTCTimestamp,
} from "lightweight-charts";
import { api, type Candle } from "@/lib/api";
import type { Signal, Analysis } from "@/lib/types";

// Seconds per bar — used to bucket live ticks into the current forming candle.
const TF_SECONDS: Record<string, number> = { M30: 1800, H1: 3600, H4: 14400, D1: 86400 };

const UP = "#22c55e";
const DOWN = "#ef4444";
const BRAND = "#6366f1";

function priceFormatFor(pair: string): { precision: number; minMove: number } {
  if (pair === "XAUUSD") return { precision: 2, minMove: 0.01 };
  if (pair === "BTCUSD") return { precision: 1, minMove: 0.1 };
  if (pair === "V100" || pair === "V25") return { precision: 2, minMove: 0.01 };
  if (pair.endsWith("JPY")) return { precision: 3, minMove: 0.001 };
  return { precision: 5, minMove: 0.00001 }; // standard forex
}

// "2026-06-24 12:00" (UTC) -> unix seconds, snapped to the bar's open.
function timeToBar(s: string | undefined, step: number): UTCTimestamp | null {
  if (!s) return null;
  const ms = Date.parse(s.replace(" ", "T") + ":00Z");
  if (Number.isNaN(ms)) return null;
  const sec = Math.floor(ms / 1000);
  return (Math.floor(sec / step) * step) as UTCTimestamp;
}

function isBull(kind?: string): boolean {
  const k = (kind || "").toLowerCase();
  return k.includes("bull") || k.includes("support") || k.includes("demand") || k.includes("rbs");
}

export function LiveChart({
  pair,
  tf,
  signal,
  annotate = false,
}: {
  pair: string;
  tf: string;
  signal?: Partial<Signal> | null;
  annotate?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lastBarRef = useRef<CandlestickData | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const [live, setLive] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [legend, setLegend] = useState<{ obs: number; bbs: number; fvgs: number; snr: number; sweeps: number; qms: number } | null>(null);

  // Create the chart once.
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: "#9aa4b2",
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      timeScale: { borderColor: "rgba(255,255,255,0.08)", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 0 },
    });
    const series = chart.addCandlestickSeries({
      upColor: UP, downColor: DOWN, borderUpColor: UP, borderDownColor: DOWN,
      wickUpColor: UP, wickDownColor: DOWN,
    });
    chartRef.current = chart;
    seriesRef.current = series;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      priceLinesRef.current = [];
    };
  }, []);

  // Load history + keep it in sync (every 20s). Resets when pair/tf changes.
  useEffect(() => {
    let alive = true;
    const series = seriesRef.current;
    if (!series) return;
    const { precision, minMove } = priceFormatFor(pair);
    series.applyOptions({ priceFormat: { type: "price", precision, minMove } });

    const loadHistory = async () => {
      try {
        const r = await api.candles(pair, tf, 400);
        if (!alive || !seriesRef.current) return;
        if (r.error || !r.candles.length) {
          setErr(r.error ? `No data for ${pair} ${tf}` : null);
          return;
        }
        setErr(null);
        const data = r.candles.map((c: Candle) => ({
          time: c.time as UTCTimestamp,
          open: c.open, high: c.high, low: c.low, close: c.close,
        }));
        seriesRef.current.setData(data);
        lastBarRef.current = data[data.length - 1];
        if (r.live != null) setLive(r.live);
      } catch {
        if (alive) setErr(`Cannot reach API for ${pair} ${tf}`);
      }
    };

    loadHistory().then(() => chartRef.current?.timeScale().fitContent());
    const histTimer = setInterval(loadHistory, 20000);
    return () => { alive = false; clearInterval(histTimer); };
  }, [pair, tf]);

  // Poll the live WS quote every 2s and extend the forming candle in real time.
  useEffect(() => {
    let alive = true;
    const step = TF_SECONDS[tf] ?? 1800;
    const poll = async () => {
      try {
        const { price } = await api.live(pair);
        if (!alive || price == null || !seriesRef.current) return;
        setLive(price);
        const nowSec = Math.floor(Date.now() / 1000);
        const barStart = (Math.floor(nowSec / step) * step) as UTCTimestamp;
        const last = lastBarRef.current;
        let bar: CandlestickData;
        if (last && (last.time as number) === barStart) {
          bar = { time: barStart, open: last.open, high: Math.max(last.high, price), low: Math.min(last.low, price), close: price };
        } else if (last && barStart > (last.time as number)) {
          bar = { time: barStart, open: price, high: price, low: price, close: price };
        } else { return; }
        seriesRef.current.update(bar);
        lastBarRef.current = bar;
      } catch { /* transient */ }
    };
    const liveTimer = setInterval(poll, 2000);
    poll();
    return () => { alive = false; clearInterval(liveTimer); };
  }, [pair, tf]);

  // Draw annotations: signal Entry/SL/TP + POI zones + structure markers.
  useEffect(() => {
    let alive = true;
    const series = seriesRef.current;
    if (!series) return;
    const { precision } = priceFormatFor(pair);
    const step = TF_SECONDS[tf] ?? 1800;
    const fmt = (n: number) => n.toFixed(precision);

    const clearOverlays = () => {
      for (const pl of priceLinesRef.current) { try { series.removePriceLine(pl); } catch { /* gone */ } }
      priceLinesRef.current = [];
      series.setMarkers([]);
    };

    const addLine = (price: number, color: string, title: string, opts?: { dashed?: boolean; width?: 1 | 2 }) => {
      priceLinesRef.current.push(series.createPriceLine({
        price, color, title,
        lineWidth: opts?.width ?? 1,
        lineStyle: opts?.dashed ? LineStyle.Dashed : LineStyle.Solid,
        axisLabelVisible: true,
      }));
    };

    const draw = async () => {
      clearOverlays();
      const markers: SeriesMarker<UTCTimestamp>[] = [];

      // 1) The signal itself — Entry / SL / TP (bold) + its POI zone.
      if (signal?.entry != null) {
        const dir = signal.direction === "short" ? "short" : "long";
        addLine(signal.entry, BRAND, `ENTRY ${fmt(signal.entry)}`, { width: 2 });
        if (signal.stop != null) addLine(signal.stop, DOWN, `SL ${fmt(signal.stop)}`, { width: 2 });
        if (signal.target != null) addLine(signal.target, UP, `TP ${fmt(signal.target)}`, { width: 2 });
        if (signal.zone_top != null) addLine(signal.zone_top, "#eab308", `${(signal.zone_kind || "POI").toUpperCase()} top`, { dashed: true });
        if (signal.zone_bottom != null) addLine(signal.zone_bottom, "#eab308", `${(signal.zone_kind || "POI").toLowerCase()} bottom`, { dashed: true });
        const st = timeToBar(signal.time, step);
        if (st != null) markers.push({
          time: st, position: dir === "long" ? "belowBar" : "aboveBar",
          color: dir === "long" ? UP : DOWN, shape: dir === "long" ? "arrowUp" : "arrowDown",
          text: `${dir.toUpperCase()} signal`,
        });
      }

      // 2) Broader POIs + structure from the analysis endpoint.
      if (annotate) {
        try {
          const a: Analysis = await api.analysis(pair, tf);
          if (!alive || !seriesRef.current) return;
          const zone = (z: { top: number; bottom: number; kind?: string }, tag: string) => {
            const col = isBull(z.kind) ? "rgba(34,197,94,0.55)" : "rgba(239,68,68,0.55)";
            addLine(z.top, col, tag, { dashed: true });
            addLine(z.bottom, col, "", { dashed: true });
          };
          (a.order_blocks || []).slice(0, 3).forEach((z) => zone(z, `OB ${z.kind?.[0]?.toUpperCase() ?? ""}`));
          (a.breakers || []).slice(0, 2).forEach((z) => zone(z, "BB"));
          (a.fresh_snr || []).slice(0, 3).forEach((z) => zone(z, "SNR"));
          (a.fvgs || []).slice(0, 2).forEach((z) => zone(z, "FVG"));

          (a.breaks || []).slice(0, 6).forEach((b) => {
            const t = timeToBar(b.time, step);
            if (t != null) markers.push({
              time: t, position: b.dir === "up" ? "belowBar" : "aboveBar",
              color: b.type === "CHoCH" ? BRAND : "#9aa4b2", shape: "circle",
              text: `${b.type}${b.dir === "up" ? "↑" : "↓"}`,
            });
          });
          (a.sweeps || []).slice(0, 6).forEach((s) => {
            const t = timeToBar(s.time, step);
            if (t != null) markers.push({
              time: t, position: s.side === "SSL" ? "belowBar" : "aboveBar",
              color: "#f59e0b", shape: "circle", text: `${s.side} swept`,
            });
          });
          (a.quasimodos || []).slice(0, 4).forEach((q) => {
            const t = timeToBar(q.time, step);
            if (t != null) markers.push({
              time: t, position: q.kind === "bullish" ? "belowBar" : "aboveBar",
              color: "#a855f7", shape: "circle", text: "QM",
            });
          });
          setLegend({
            obs: a.order_blocks?.length ?? 0, bbs: a.breakers?.length ?? 0,
            fvgs: a.fvgs?.length ?? 0, snr: a.fresh_snr?.length ?? 0,
            sweeps: a.sweeps?.length ?? 0, qms: a.quasimodos?.length ?? 0,
          });
        } catch { /* analysis not ready — keep signal lines */ }
      }

      // markers must be sorted ascending by time for lightweight-charts
      markers.sort((m1, m2) => (m1.time as number) - (m2.time as number));
      if (alive && seriesRef.current) seriesRef.current.setMarkers(markers);
    };

    draw();
    return () => { alive = false; clearOverlays(); };
    // re-run when the signal identity or pair/tf/annotate changes
  }, [pair, tf, annotate, signal?.entry, signal?.stop, signal?.target, signal?.time]);

  const { precision } = priceFormatFor(pair);
  return (
    <div className="w-full rounded-xl border border-line overflow-hidden bg-[#131722]">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-line">
        <span className="text-xs text-sub">
          {pair} · {tf} · <span className="text-ink">live</span> · Finnhub WebSocket
          {signal?.entry != null && <span className="text-brand"> · signal overlay</span>}
        </span>
        {live != null && <span className="font-mono text-xs text-ink">{live.toFixed(precision)}</span>}
      </div>
      <div ref={containerRef} className="h-[480px] w-full" />
      {annotate && legend && (
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-sub px-3 py-1.5 border-t border-line">
          <span>POIs drawn:</span>
          <span className="text-up">OB {legend.obs}</span>
          <span className="text-up">BB {legend.bbs}</span>
          <span className="text-down">FVG {legend.fvgs}</span>
          <span>SNR {legend.snr}</span>
          <span className="text-amber-400">sweeps {legend.sweeps}</span>
          <span className="text-purple-400">QM {legend.qms}</span>
          <span className="text-sub">· markers = CHoCH/BOS/sweep/QM at their bar</span>
        </div>
      )}
      {err && <p className="text-[11px] text-amber-400/90 px-3 py-1.5 border-t border-line">{err}</p>}
    </div>
  );
}

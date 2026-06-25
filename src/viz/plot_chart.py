"""Full annotated chart: candles + SNR zones + market structure + rejections.

Everything is computed on the full history (correct context) then a focused
window is drawn. Signal charts center on the setup bar with the exact SNR zone,
entry/SL/TP, and confluence labels.

Usage:
    python -m src.viz.plot_chart --pair EURUSD --timeframe H4 --bars 160
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import config
from src.data.fetch import load
from src.detectors import rejection, smc, snr
from src.detectors.structure import analyze

CHARTS_DIR = config.ROOT / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

UP, DOWN = "#26a69a", "#ef5350"
SUP, RES = "#2e7d32", "#c62828"


def _window(full_len: int, bars: int, signal_bar: int | None) -> tuple[int, int]:
    """Pick [start, end) so signal bar sits ~45% from the left edge."""
    if signal_bar is not None and full_len > 0:
        lead = int(bars * 0.45)
        start = max(0, signal_bar - lead)
        end = min(full_len, start + bars)
        start = max(0, end - bars)
        return start, end
    return max(0, full_len - bars), full_len


def _candles(ax, df) -> None:
    for x, (_, row) in enumerate(df.iterrows()):
        color = UP if row["close"] >= row["open"] else DOWN
        ax.vlines(x, row["low"], row["high"], color=color, linewidth=0.8, zorder=2)
        lo = min(row["open"], row["close"])
        height = abs(row["close"] - row["open"]) or (row["high"] - row["low"]) * 1e-3
        ax.add_patch(Rectangle((x - 0.3, lo), 0.6, height, color=color, zorder=3))


def _in_view(lo: float, hi: float, ymin: float, ymax: float) -> bool:
    return lo <= ymax and hi >= ymin


def plot(pair: str, timeframe: str, bars: int, left: int, right: int,
         entry: float | None = None, stop: float | None = None,
         target: float | None = None, direction: str | None = None,
         signal_bar: int | None = None, zone_top: float | None = None,
         zone_bottom: float | None = None, zone_kind: str | None = None,
         confluences: list[str] | None = None) -> str:
    full = load(pair, timeframe)
    res = analyze(full, left, right)
    zones = snr.detect(full, left, right)
    rej = rejection.detect(full)
    last_idx = len(full) - 1
    ref_idx = signal_bar if signal_bar is not None else last_idx

    start, end = _window(len(full), bars, signal_bar)
    view = full.iloc[start:end].reset_index()
    n = len(view)
    pos = {orig: x for x, orig in enumerate(range(start, end))}
    ymin, ymax = view["low"].min(), view["high"].max()

    if entry is not None:
        ymin = min(ymin, entry, stop or entry, target or entry)
        ymax = max(ymax, entry, stop or entry, target or entry)
    if zone_top is not None and zone_bottom is not None:
        ymin = min(ymin, zone_bottom)
        ymax = max(ymax, zone_top)
    pad = (ymax - ymin) * 0.06 or 0.0001
    ymin -= pad
    ymax += pad

    fig, ax = plt.subplots(figsize=(18, 9), facecolor="#0e1116")
    ax.set_facecolor("#131820")
    ax.set_ylim(ymin, ymax)
    _candles(ax, view)

    # --- SNR zones fresh at signal bar (or last bar for overview charts) ---
    fresh_zones = [
        z for z in zones
        if z.is_fresh_at(ref_idx) and _in_view(z.bottom, z.top, ymin, ymax)
    ]
    for z in fresh_zones:
        x0 = pos.get(z.anchor_idx, 0)
        color = SUP if z.kind == "support" else RES
        ax.add_patch(Rectangle((x0, z.bottom), n - x0, z.top - z.bottom,
                               color=color, alpha=0.14, zorder=1, lw=0))
        ax.hlines([z.top, z.bottom], x0, n, color=color, linewidth=0.7, alpha=0.55, zorder=1)
        ax.annotate(f"{z.kind[:3].upper()} fresh", (n - 0.5, z.mid()), fontsize=7.5,
                    color=color, ha="right", va="center", fontweight="bold")

    # --- Signal SNR zone (the exact level that triggered the setup) ---
    if zone_top is not None and zone_bottom is not None:
        zk = zone_kind or "snr"
        zcol = SUP if zk == "support" else RES
        ax.add_patch(Rectangle((0, zone_bottom), n, zone_top - zone_bottom,
                               color=zcol, alpha=0.22, zorder=4, lw=0))
        ax.hlines([zone_top, zone_bottom], 0, n, color=zcol, linewidth=1.4,
                  linestyle="-", alpha=0.9, zorder=4)
        ax.annotate(f"★ SIGNAL {zk.upper()}", (1, zone_top), fontsize=8,
                    color=zcol, ha="left", va="bottom", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#0e1116",
                              edgecolor=zcol, alpha=0.9, lw=0.8))

    # --- structure swings + breaks ---
    for s in res["swings"]:
        if s.idx < start or s.idx >= end:
            continue
        x = pos[s.idx]
        ax.scatter(x, s.price, s=16, color="#8b949e", zorder=4)
        ax.annotate(s.label, (x, s.price), textcoords="offset points",
                    xytext=(0, 8 if s.kind == "H" else -14), ha="center", fontsize=7.5,
                    color="#1565c0" if s.label in ("HH", "HL") else "#c62828", fontweight="bold")
    for b in res["breaks"]:
        if b.idx < start or b.idx >= end:
            continue
        x = pos[b.idx]
        x0 = pos.get(b.level_idx, 0)
        c = "#ab47bc" if b.kind == "CHoCH" else "#546e7a"
        ax.hlines(b.level, x0, x, color=c, linestyles="--", linewidth=1.1, zorder=2)
        ax.annotate(b.kind, (x, b.level), textcoords="offset points",
                    xytext=(4, 4 if b.direction == "up" else -12), fontsize=7, color=c,
                    fontweight="bold")

    # --- rejection candles ---
    rv = rej.iloc[start:end].reset_index(drop=True)
    strong = 0.55
    for x in range(n):
        if rv["bull_rej"].iat[x] and rv["strength"].iat[x] >= strong:
            ax.scatter(x, view["low"].iat[x] - pad * 0.3, marker="^",
                       s=40, color="#43a047", zorder=5, edgecolors="white", linewidths=0.4)
            if signal_bar is not None and start + x == signal_bar:
                ax.annotate("REJ", (x, view["low"].iat[x]), textcoords="offset points",
                            xytext=(0, -16), ha="center", fontsize=8, color="#43a047",
                            fontweight="bold")
        if rv["bear_rej"].iat[x] and rv["strength"].iat[x] >= strong:
            ax.scatter(x, view["high"].iat[x] + pad * 0.3, marker="v",
                       s=40, color="#e53935", zorder=5, edgecolors="white", linewidths=0.4)
            if signal_bar is not None and start + x == signal_bar:
                ax.annotate("REJ", (x, view["high"].iat[x]), textcoords="offset points",
                            xytext=(0, 14), ha="center", fontsize=8, color="#e53935",
                            fontweight="bold")

    # --- SMC POIs ---
    OB_BULL, OB_BEAR, FVG_C, SWP = "#1b5e20", "#b71c1c", "#f9a825", "#8e24aa"
    obs = [o for o in smc.order_blocks(full, left, right)
           if start <= o.idx < end and o.mitigated_idx is None
           and _in_view(o.bottom, o.top, ymin, ymax)][-8:]
    for ob in obs:
        x0 = pos[ob.idx]
        col = OB_BULL if ob.kind == "bullish" else OB_BEAR
        w = min(18, n - x0)
        ax.add_patch(Rectangle((x0, ob.bottom), w, ob.top - ob.bottom, facecolor=col,
                               alpha=0.12, edgecolor=col, lw=1.0, ls=":", zorder=1))
        ax.annotate("OB", (x0 + 0.3, (ob.top + ob.bottom) / 2), fontsize=7.5, color=col,
                    fontweight="bold", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#0e1116", alpha=0.75, lw=0))

    fvgs = [f for f in smc.fair_value_gaps(full)
            if start <= f.idx < end and f.mitigated_idx is None
            and _in_view(f.bottom, f.top, ymin, ymax)][-6:]
    for f in fvgs:
        x0 = pos[f.idx]
        ax.add_patch(Rectangle((x0, f.bottom), min(12, n - x0), f.top - f.bottom,
                               facecolor=FVG_C, alpha=0.22, edgecolor=FVG_C, lw=0.6, zorder=1))
        ax.annotate("FVG", (x0 + 0.3, f.top), fontsize=7, color="#e65100", fontweight="bold")

    for sw in [s for s in smc.liquidity_sweeps(full, left, right) if start <= s.idx < end][-10:]:
        x = pos[sw.idx]
        lbl = "BSL" if sw.direction == "bsl" else "SSL"
        ax.scatter(x, sw.level, marker="X", s=55, color=SWP, zorder=5, linewidths=1.6)
        ax.annotate(lbl, (x, sw.level), textcoords="offset points",
                    xytext=(5, 3), fontsize=7.5, color=SWP, fontweight="bold")

    breakers = [b for b in smc.breaker_blocks(full, left, right)
                if start <= b.idx < end and _in_view(b.bottom, b.top, ymin, ymax)][-5:]
    for bb in breakers:
        x0 = pos[bb.idx]
        col = "#0288d1" if bb.kind == "bullish" else "#f4511e"
        ax.add_patch(Rectangle((x0, bb.bottom), min(22, n - x0), bb.top - bb.bottom,
                               facecolor=col, alpha=0.12, edgecolor=col, lw=1.0, ls="--", zorder=1))
        ax.annotate("BB", (x0 + 0.3, bb.top), fontsize=7.5, color=col, fontweight="bold")

    qms = [q for q in smc.quasimodos(full, left, right) if start <= q.idx < end][-5:]
    for qm in qms:
        x0 = pos[qm.idx]
        col = "#1565c0" if qm.kind == "bullish" else "#c62828"
        ax.scatter(x0, qm.sweep_level, s=55, color=col, marker="*", zorder=6, edgecolors="white",
                   linewidths=0.5)
        ax.annotate("QM", (x0, qm.sweep_level), textcoords="offset points",
                    xytext=(0, 8 if qm.kind == "bearish" else -14), ha="center",
                    fontsize=8, color=col, fontweight="bold")

    # -----------------------------------------------------------------------
    # SIGNAL OVERLAY
    # -----------------------------------------------------------------------
    long = (direction or "long") == "long"
    entry_c = "#26a69a" if long else "#ef5350"
    sl_c = "#ef5350" if long else "#26a69a"
    tp_c = "#66bb6a"

    if entry is not None and stop is not None and target is not None:
        half = abs(entry - stop) * 0.5
        ax.add_patch(Rectangle((0, entry - half), n, half * 2,
                               facecolor=entry_c, alpha=0.1, zorder=6, lw=0))

        ax.hlines(entry, 0, n, color=entry_c, linewidth=2.0, linestyles="-", zorder=7)
        ax.annotate(f"ENTRY  {entry:.5f}", (n - 0.5, entry), fontsize=9,
                    color=entry_c, va="center", ha="right", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#0e1116", alpha=0.9, lw=0))

        ax.hlines(stop, 0, n, color=sl_c, linewidth=1.6, linestyles="--", zorder=7)
        ax.annotate(f"SL  {stop:.5f}", (n - 0.5, stop), fontsize=8.5,
                    color=sl_c, va="center", ha="right",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#0e1116", alpha=0.85, lw=0))

        ax.hlines(target, 0, n, color=tp_c, linewidth=1.6, linestyles="--", zorder=7)
        ax.annotate(f"TP  {target:.5f}", (n - 0.5, target), fontsize=8.5,
                    color=tp_c, va="center", ha="right",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#0e1116", alpha=0.85, lw=0))

        if signal_bar is not None and signal_bar in pos:
            sx = pos[signal_bar]
            ax.axvline(sx, color=entry_c, linestyle=":", linewidth=1.2, alpha=0.75, zorder=8)
            ax.scatter(sx, entry, s=120, color=entry_c, marker="D", zorder=9,
                       edgecolors="white", linewidths=1.2)
            ax.annotate("SIGNAL", (sx, entry), textcoords="offset points",
                        xytext=(12, 0), fontsize=8, color=entry_c, fontweight="bold", va="center")

        rr = abs(target - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        title = (f"{pair} {timeframe}  ·  {'▲ LONG' if long else '▼ SHORT'}"
                 f"  ·  1:{rr:.1f}R  ·  OB · FVG · BB · QM · BSL/SSL")
        suffix = f"_sig_{int(entry * 1e5)}"
        last_bar = full.index[-1]
        last_ts = pd.Timestamp(last_bar).strftime("%Y-%m-%d %H:%M UTC")
        title += f"  ·  data through {last_ts}"
    else:
        title = f"{pair} {timeframe} — SNR · structure · OB/FVG · BB/QM · BSL/SSL"
        suffix = "_full"

    last_bar = full.index[-1]
    last_ts = pd.Timestamp(last_bar).strftime("%Y-%m-%d %H:%M UTC")
    if entry is None or stop is None or target is None:
        title += f"  ·  data through {last_ts}"

    # Confluence / reason callout (top-left)
    if confluences:
        lines = ["WHY THIS SETUP:"] + [f"• {c}" for c in confluences[:7]]
        ax.text(0.015, 0.98, "\n".join(lines), transform=ax.transAxes,
                va="top", ha="left", fontsize=7.5, color="#e6edf3", linespacing=1.35,
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#0e1116",
                          edgecolor="#30363d", alpha=0.92, lw=0.8),
                family="monospace", zorder=20)

    # POI legend (bottom-left)
    legend = "POI:  OB=Order Block  BB=Breaker  QM=Quasimodo  BSL/SSL=Liquidity  FVG=Gap"
    ax.text(0.015, 0.02, legend, transform=ax.transAxes, fontsize=7, color="#8b949e",
            va="bottom", ha="left", zorder=20)

    ticks = range(0, n, max(1, n // 14))
    ax.set_xticks(list(ticks))
    times = view["time"] if "time" in view.columns else view.index
    ax.set_xticklabels([pd.Timestamp(times.iloc[t]).strftime("%m-%d %H:%M") for t in ticks],
                       rotation=40, fontsize=7.5, color="#8b949e")
    ax.set_title(title, color="#e6edf3", fontsize=11, pad=12, fontweight="bold")
    ax.set_ylabel("price", color="#8b949e")
    ax.tick_params(colors="#8b949e")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.margins(x=0.01)
    ax.grid(True, alpha=0.1, color="#30363d")
    fig.tight_layout()

    out = CHARTS_DIR / f"{pair}_{timeframe}{suffix}.png"
    fig.savefig(out, dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved {out}")
    return str(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Full annotated MSNR chart.")
    p.add_argument("--pair", default="EURUSD", choices=list(config.PAIRS))
    p.add_argument("--timeframe", default="H4", choices=list(config.TIMEFRAMES))
    p.add_argument("--bars", type=int, default=160)
    p.add_argument("--left", type=int, default=3)
    p.add_argument("--right", type=int, default=3)
    args = p.parse_args(argv)
    plot(args.pair, args.timeframe, args.bars, args.left, args.right)
    return 0


if __name__ == "__main__":
    sys.exit(main())

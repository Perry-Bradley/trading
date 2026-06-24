"""Full annotated chart: candles + SNR zones + market structure + rejections.

Everything is computed on the full history (correct context) then the last
`--bars` are drawn. SNR zones still fresh at the right edge are drawn solid and
labelled; spent/flipped zones are faint.

Usage:
    python -m src.viz.plot_chart --pair EURUSD --timeframe H4 --bars 160
"""
from __future__ import annotations

import argparse
import sys

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


def _candles(ax, df) -> None:
    for x, (_, row) in enumerate(df.iterrows()):
        color = UP if row["close"] >= row["open"] else DOWN
        ax.vlines(x, row["low"], row["high"], color=color, linewidth=0.8, zorder=2)
        lo = min(row["open"], row["close"])
        height = abs(row["close"] - row["open"]) or (row["high"] - row["low"]) * 1e-3
        ax.add_patch(Rectangle((x - 0.3, lo), 0.6, height, color=color, zorder=3))


def plot(pair: str, timeframe: str, bars: int, left: int, right: int,
         entry: float | None = None, stop: float | None = None,
         target: float | None = None, direction: str | None = None) -> str:
    full = load(pair, timeframe)
    res = analyze(full, left, right)
    zones = snr.detect(full, left, right)
    rej = rejection.detect(full)
    last_idx = len(full) - 1

    start = max(0, len(full) - bars)
    view = full.iloc[start:].reset_index()
    n = len(view)
    pos = {orig: x for x, orig in enumerate(range(start, len(full)))}
    ymin, ymax = view["low"].min(), view["high"].max()

    # Expand y-range to include signal levels if they're outside the visible window
    if entry is not None:
        ymin = min(ymin, entry, stop or entry, target or entry) * 0.9995
        ymax = max(ymax, entry, stop or entry, target or entry) * 1.0005

    fig, ax = plt.subplots(figsize=(17, 8.5), facecolor="#0e1116")
    ax.set_facecolor("#131820")
    _candles(ax, view)

    # --- SNR zones: only the FRESH (actionable) ones, drawn as clean bands ---
    fresh_zones = [z for z in zones if z.is_fresh_at(last_idx) and ymin <= z.mid() <= ymax]
    for z in fresh_zones:
        x0 = pos.get(z.anchor_idx)
        if x0 is None:                      # anchored before the window — span from left
            x0 = 0
        color = SUP if z.kind == "support" else RES
        ax.add_patch(Rectangle((x0, z.bottom), n - x0, z.top - z.bottom,
                               color=color, alpha=0.16, zorder=1, lw=0))
        ax.hlines([z.top, z.bottom], x0, n, color=color, linewidth=0.6, alpha=0.5, zorder=1)
        ax.annotate(f"{z.kind[:3]} fresh", (n - 1, z.mid()), fontsize=7,
                    color=color, ha="right", va="center", fontweight="bold")

    # --- structure swings + breaks ---
    for s in res["swings"]:
        if s.idx < start:
            continue
        x = pos[s.idx]
        ax.scatter(x, s.price, s=14, color="#8b949e", zorder=4)
        ax.annotate(s.label, (x, s.price), textcoords="offset points",
                    xytext=(0, 7 if s.kind == "H" else -13), ha="center", fontsize=7,
                    color="#1565c0" if s.label in ("HH", "HL") else "#c62828")
    for b in res["breaks"]:
        if b.idx < start:
            continue
        x = pos[b.idx]
        x0 = pos.get(b.level_idx, 0)
        c = "#6a1b9a" if b.kind == "CHoCH" else "#455a64"
        ax.hlines(b.level, x0, x, color=c, linestyles="--", linewidth=1.0, zorder=2)
        ax.annotate(b.kind, (x, b.level), textcoords="offset points",
                    xytext=(3, 3 if b.direction == "up" else -11), fontsize=6.5, color=c)

    # --- rejection candles (only strong ones, to cut noise) ---
    rv = rej.iloc[start:].reset_index(drop=True)
    strong = 0.62
    for x in range(n):
        if rv["bull_rej"].iat[x] and rv["strength"].iat[x] >= strong:
            ax.scatter(x, view["low"].iat[x] - (ymax - ymin) * 0.012, marker="^",
                       s=26, color="#2e7d32", zorder=5)
        if rv["bear_rej"].iat[x] and rv["strength"].iat[x] >= strong:
            ax.scatter(x, view["high"].iat[x] + (ymax - ymin) * 0.012, marker="v",
                       s=26, color="#c62828", zorder=5)

    # --- SMC POIs: order blocks, FVGs, liquidity sweeps (recent + unmitigated) ---
    OB_BULL, OB_BEAR, FVG_C, SWP = "#1b5e20", "#b71c1c", "#f9a825", "#6a1b9a"
    obs = [o for o in smc.order_blocks(full, left, right)
           if o.idx >= start and o.mitigated_idx is None and ymin <= o.bottom <= ymax][-5:]
    for ob in obs:
        x0 = pos[ob.idx]
        col = OB_BULL if ob.kind == "bullish" else OB_BEAR
        ax.add_patch(Rectangle((x0, ob.bottom), n - x0, ob.top - ob.bottom, facecolor=col,
                               alpha=0.09, edgecolor=col, lw=0.7, ls=":", zorder=1))
        ax.annotate("OB", (x0, ob.top), fontsize=6.5, color=col, fontweight="bold")
    fvgs = [f for f in smc.fair_value_gaps(full)
            if f.idx >= start and f.mitigated_idx is None and ymin <= f.bottom <= ymax][-5:]
    for f in fvgs:
        x0 = pos[f.idx]
        ax.add_patch(Rectangle((x0, f.bottom), min(10, n - x0), f.top - f.bottom,
                               facecolor=FVG_C, alpha=0.18, edgecolor=FVG_C, lw=0.5, zorder=1))
        ax.annotate("FVG", (x0, f.top), fontsize=6, color="#9c6f00")
    for sw in [s for s in smc.liquidity_sweeps(full, left, right) if s.idx >= start][-8:]:
        x = pos[sw.idx]
        ax.scatter(x, sw.level, marker="x", s=32, color=SWP, zorder=5, linewidths=1.4)
        lbl = "BSL" if sw.direction == "bsl" else "SSL"
        ax.annotate(lbl, (x, sw.level), textcoords="offset points",
                    xytext=(3, 2), fontsize=6, color=SWP, fontweight="bold")

    # --- SMC POIs: Breakers & Quasimodos ---
    breakers = [b for b in smc.breaker_blocks(full, left, right) 
                if b.idx >= start and ymin <= b.bottom <= ymax][-4:]
    for bb in breakers:
        x0 = pos[bb.idx]
        col = "#0277bd" if bb.kind == "bullish" else "#d84315"
        ax.add_patch(Rectangle((x0, bb.bottom), min(20, n - x0), bb.top - bb.bottom, facecolor=col,
                               alpha=0.1, edgecolor=col, lw=0.8, ls="--", zorder=1))
        ax.annotate("BB", (x0, bb.top), fontsize=6.5, color=col, fontweight="bold")
        
    qms = [q for q in smc.quasimodos(full, left, right) if q.idx >= start][-4:]
    for qm in qms:
        x0 = pos[qm.idx]
        col = "#1565c0" if qm.kind == "bullish" else "#c62828"
        ax.scatter(x0, qm.sweep_level, s=30, color=col, marker="*", zorder=6)
        ax.annotate("QM", (x0, qm.sweep_level), textcoords="offset points",
                    xytext=(0, 5 if qm.kind == "bearish" else -12), ha="center",
                    fontsize=7, color=col, fontweight="bold")

    # -----------------------------------------------------------------------
    # SIGNAL OVERLAY — draws the exact trade setup on the chart
    # -----------------------------------------------------------------------
    if entry is not None and stop is not None and target is not None:
        long = (direction or "long") == "long"
        entry_c = "#26a69a" if long else "#ef5350"   # teal = long, red = short
        sl_c    = "#ef5350" if long else "#26a69a"
        tp_c    = "#26a69a"                          # always green for profit

        # Shaded entry zone (entry price ± half the stop distance)
        half = abs(entry - stop) * 0.5
        ax.add_patch(Rectangle((0, entry - half), n, half * 2,
                               facecolor=entry_c, alpha=0.08, zorder=6, lw=0))

        # Solid entry line
        ax.hlines(entry, 0, n, color=entry_c, linewidth=1.8, linestyles="-", zorder=7)
        ax.annotate(f"  ENTRY  {entry:.5f}", (n - 1, entry), fontsize=9,
                    color=entry_c, va="center", ha="right", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#0e1116", alpha=0.8, lw=0))

        # Stop loss — dashed red
        ax.hlines(stop, 0, n, color=sl_c, linewidth=1.5, linestyles="--", zorder=7)
        ax.annotate(f"  SL  {stop:.5f}", (n - 1, stop), fontsize=8.5,
                    color=sl_c, va="center", ha="right",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#0e1116", alpha=0.8, lw=0))

        # Take profit — dashed green
        ax.hlines(target, 0, n, color=tp_c, linewidth=1.5, linestyles="--", zorder=7)
        ax.annotate(f"  TP  {target:.5f}", (n - 1, target), fontsize=8.5,
                    color=tp_c, va="center", ha="right",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#0e1116", alpha=0.8, lw=0))

        rr = abs(target - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 0
        title = (f"{pair} {timeframe}  ·  {'▲ LONG' if long else '▼ SHORT'}"
                 f"  ·  Entry {entry:.5f}  SL {stop:.5f}  TP {target:.5f}  (1:{rr:.1f}R)"
                 f"  ·  SNR · OB/FVG · BB/QM")
        suffix = f"_sig_{int(entry*1e5)}"
    else:
        title = f"{pair} {timeframe} — SNR · structure · rejections · OB/FVG · BB/QM · BSL/SSL"
        suffix = "_full"

    ticks = range(0, n, max(1, n // 12))
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([view["time"].iloc[t].strftime("%m-%d %H:%M") for t in ticks],
                       rotation=45, fontsize=8, color="#8b949e")
    ax.set_title(title, color="#e6edf3", fontsize=10, pad=10)
    ax.set_ylabel("price", color="#8b949e")
    ax.tick_params(colors="#8b949e")
    for spine in ax.spines.values():
        spine.set_edgecolor("#30363d")
    ax.margins(x=0.01)
    ax.grid(True, alpha=0.08, color="#30363d")
    fig.tight_layout()

    out = CHARTS_DIR / f"{pair}_{timeframe}{suffix}.png"
    fig.savefig(out, dpi=120, facecolor=fig.get_facecolor())
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

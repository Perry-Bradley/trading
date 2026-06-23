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
from src.detectors import rejection, snr
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


def plot(pair: str, timeframe: str, bars: int, left: int, right: int) -> str:
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

    fig, ax = plt.subplots(figsize=(17, 8.5))
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
        ax.scatter(x, s.price, s=14, color="black", zorder=4)
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

    ticks = range(0, n, max(1, n // 12))
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([view["time"].iloc[t].strftime("%Y-%m-%d") for t in ticks],
                       rotation=45, fontsize=8)
    ax.set_title(f"{pair} {timeframe} — SNR zones + structure + rejections")
    ax.set_ylabel("price")
    ax.margins(x=0.01)
    ax.grid(True, alpha=0.12)
    fig.tight_layout()

    out = CHARTS_DIR / f"{pair}_{timeframe}_full.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"saved {out}")
    return str(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Full annotated MSNR chart.")
    p.add_argument("--pair", default="EURUSD", choices=list(config.YF_TICKERS))
    p.add_argument("--timeframe", default="H4", choices=list(config.TIMEFRAMES))
    p.add_argument("--bars", type=int, default=160)
    p.add_argument("--left", type=int, default=3)
    p.add_argument("--right", type=int, default=3)
    args = p.parse_args(argv)
    plot(args.pair, args.timeframe, args.bars, args.left, args.right)
    return 0


if __name__ == "__main__":
    sys.exit(main())

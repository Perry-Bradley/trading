"""Render a candlestick chart annotated with market structure.

Swings are labelled HH/HL/LL/LH; BOS/CHoCH breaks are drawn as horizontal
lines at the broken level with a tag at the breaking bar.

Structure is computed on the FULL history (so trend/confirmation context is
correct), then only the last `--bars` are drawn.

Usage:
    python -m src.viz.plot_structure --pair EURUSD --timeframe H4 --bars 180
"""
from __future__ import annotations

import argparse
import sys

import matplotlib

matplotlib.use("Agg")  # headless: write a PNG, don't open a window
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import config
from src.detectors import structure as st

CHARTS_DIR = config.ROOT / "charts"
CHARTS_DIR.mkdir(exist_ok=True)

UP = "#26a69a"
DOWN = "#ef5350"


def _candles(ax, df) -> None:
    for x, (_, row) in enumerate(df.iterrows()):
        up = row["close"] >= row["open"]
        color = UP if up else DOWN
        ax.vlines(x, row["low"], row["high"], color=color, linewidth=0.8, zorder=2)
        lo = min(row["open"], row["close"])
        height = abs(row["close"] - row["open"]) or (row["high"] - row["low"]) * 1e-3
        ax.add_patch(Rectangle((x - 0.3, lo), 0.6, height, color=color, zorder=3))


def plot(pair: str, timeframe: str, bars: int, left: int, right: int) -> str:
    path = config.DATA_DIR / f"{pair}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run: python -m src.data.fetch --pair {pair}")
    import pandas as pd

    full = pd.read_parquet(path)
    res = st.analyze(full, left=left, right=right)

    start = max(0, len(full) - bars)
    view = full.iloc[start:].reset_index()
    # map original bar index -> x position in the view
    pos = {orig: x for x, orig in enumerate(range(start, len(full)))}

    fig, ax = plt.subplots(figsize=(16, 8))
    _candles(ax, view)

    rng = view["high"].max() - view["low"].min()
    pad = rng * 0.02

    for s in res["swings"]:
        if s.idx < start:
            continue
        x = pos[s.idx]
        above = s.kind == "H"
        ax.scatter(x, s.price, s=18, color="black", zorder=4)
        ax.annotate(
            s.label,
            (x, s.price),
            textcoords="offset points",
            xytext=(0, 8 if above else -14),
            ha="center",
            fontsize=8,
            color="#1565c0" if s.label in ("HH", "HL") else "#c62828",
            fontweight="bold",
        )

    for b in res["breaks"]:
        if b.idx < start:
            continue
        x = pos[b.idx]
        x0 = pos.get(b.level_idx, 0)
        is_choch = b.kind == "CHoCH"
        line_color = "#6a1b9a" if is_choch else "#455a64"
        ax.hlines(b.level, x0, x, color=line_color, linestyles="--", linewidth=1.1, zorder=1)
        ax.annotate(
            b.kind,
            (x, b.level),
            textcoords="offset points",
            xytext=(4, 4 if b.direction == "up" else -12),
            fontsize=7.5,
            color=line_color,
            fontweight="bold",
        )

    n = len(view)
    ticks = range(0, n, max(1, n // 12))
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([view["time"].iloc[t].strftime("%Y-%m-%d") for t in ticks], rotation=45, fontsize=8)
    ax.set_title(f"{pair} {timeframe} — market structure (swings, BOS, CHoCH)  [left={left} right={right}]")
    ax.set_ylabel("price")
    ax.margins(x=0.01)
    ax.grid(True, alpha=0.15)
    fig.tight_layout()

    out = CHARTS_DIR / f"{pair}_{timeframe}_structure.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    n_swings = sum(1 for s in res["swings"] if s.idx >= start)
    n_breaks = sum(1 for b in res["breaks"] if b.idx >= start)
    print(f"saved {out}  ({n_swings} swings, {n_breaks} breaks in view)")
    return str(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Plot market structure.")
    p.add_argument("--pair", default="EURUSD", choices=list(config.PAIRS))
    p.add_argument("--timeframe", default="H4", choices=list(config.TIMEFRAMES))
    p.add_argument("--bars", type=int, default=180, help="how many recent bars to draw")
    p.add_argument("--left", type=int, default=3)
    p.add_argument("--right", type=int, default=3)
    args = p.parse_args(argv)
    plot(args.pair, args.timeframe, args.bars, args.left, args.right)
    return 0


if __name__ == "__main__":
    sys.exit(main())

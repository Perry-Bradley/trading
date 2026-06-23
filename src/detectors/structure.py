"""Market-structure detection: swing points, HH/HL/LL/LH, BOS, CHoCH.

This is the foundation every other MSNR/SMC detector builds on. Two ideas drive
the design:

1. **Causality.** A swing pivot at bar i is only *confirmed* once `right` bars
   have printed after it (you can't know it's a pivot until price turns). All
   structure breaks are likewise confirmed on a candle *close* through a level,
   never on an intrabar wick. This keeps the output usable in a backtest without
   lookahead bias.

2. **Definitions follow the course** (Lesson 2 & 6):
     - Uptrend  = Higher Highs (HH) + Higher Lows (HL)
     - Downtrend = Lower Lows (LL) + Lower Highs (LH)
     - BOS  = close breaks structure in the trend direction (continuation)
     - CHoCH = close breaks structure against the trend (possible reversal)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


@dataclass
class Swing:
    idx: int            # bar position in the frame
    time: pd.Timestamp
    kind: str           # "H" (swing high) or "L" (swing low)
    price: float
    label: str          # HH / HL / LL / LH (or H / L for the first of each kind)


@dataclass
class Break:
    idx: int            # bar where the breaking close printed
    time: pd.Timestamp
    direction: str      # "up" or "down"
    kind: str           # "BOS" or "CHoCH"
    level: float        # the swing price that was broken
    level_idx: int      # bar position of the swing that was broken


def find_pivots(df: pd.DataFrame, left: int = 3, right: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks of fractal swing highs / lows.

    A swing high is the strict maximum high over a window of `left` bars before
    and `right` bars after it (ties resolve to the earliest bar, so flat tops
    aren't double-counted). Swing lows are symmetric.
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    is_high = np.zeros(n, dtype=bool)
    is_low = np.zeros(n, dtype=bool)
    for i in range(left, n - right):
        win_h = highs[i - left : i + right + 1]
        if highs[i] == win_h.max() and win_h.argmax() == left:
            is_high[i] = True
        win_l = lows[i - left : i + right + 1]
        if lows[i] == win_l.min() and win_l.argmin() == left:
            is_low[i] = True
    return is_high, is_low


def _alternating_swings(df: pd.DataFrame, is_high: np.ndarray, is_low: np.ndarray) -> list[Swing]:
    """Collapse raw pivots into a clean alternating H, L, H, L ... sequence.

    When two pivots of the same kind occur in a row (no opposite pivot between
    them) we keep the more extreme one — that's the swing that matters.
    """
    raw: list[tuple[int, str, float]] = []
    for i in range(len(df)):
        if is_high[i]:
            raw.append((i, "H", float(df["high"].iat[i])))
        if is_low[i]:
            raw.append((i, "L", float(df["low"].iat[i])))
    raw.sort(key=lambda e: (e[0], e[1]))  # by bar, "H" before "L" on ties

    cleaned: list[tuple[int, str, float]] = []
    for e in raw:
        if not cleaned or e[1] != cleaned[-1][1]:
            cleaned.append(e)
            continue
        # same kind as previous -> keep the more extreme
        if e[1] == "H" and e[2] >= cleaned[-1][2]:
            cleaned[-1] = e
        elif e[1] == "L" and e[2] <= cleaned[-1][2]:
            cleaned[-1] = e

    swings: list[Swing] = []
    last_high = last_low = None
    for idx, kind, price in cleaned:
        if kind == "H":
            label = "H" if last_high is None else ("HH" if price > last_high else "LH")
            last_high = price
        else:
            label = "L" if last_low is None else ("HL" if price > last_low else "LL")
            last_low = price
        swings.append(Swing(idx, df.index[idx], kind, price, label))
    return swings


def _structure_breaks(df: pd.DataFrame, swings: list[Swing], right: int) -> list[Break]:
    """Detect BOS / CHoCH from confirmed swings using close-through breaks.

    Walks bars forward. A swing only becomes an actionable reference `right` bars
    after it forms (confirmation lag). The most recent confirmed swing high is
    the level to break for an up-move; the most recent swing low for a down-move.
    """
    closes = df["close"].to_numpy()
    times = df.index
    swings_sorted = sorted(swings, key=lambda s: s.idx)

    breaks: list[Break] = []
    trend = 0  # +1 bull, -1 bear, 0 undetermined
    ref_high: tuple[int, float] | None = None
    ref_low: tuple[int, float] | None = None
    broken_high = broken_low = False
    si = 0

    for b in range(len(df)):
        # Activate swings whose confirmation (idx + right) has been reached.
        while si < len(swings_sorted) and swings_sorted[si].idx + right <= b:
            s = swings_sorted[si]
            si += 1
            if s.kind == "H":
                ref_high, broken_high = (s.idx, s.price), False
            else:
                ref_low, broken_low = (s.idx, s.price), False

        c = closes[b]
        if ref_high and not broken_high and c > ref_high[1]:
            kind = "CHoCH" if trend == -1 else "BOS"
            trend, broken_high = 1, True
            breaks.append(Break(b, times[b], "up", kind, ref_high[1], ref_high[0]))
        if ref_low and not broken_low and c < ref_low[1]:
            kind = "CHoCH" if trend == 1 else "BOS"
            trend, broken_low = -1, True
            breaks.append(Break(b, times[b], "down", kind, ref_low[1], ref_low[0]))

    return breaks


def analyze(df: pd.DataFrame, left: int = 3, right: int = 3) -> dict:
    """Run full market-structure analysis on an OHLC frame.

    Returns {"swings": [Swing...], "breaks": [Break...]}.
    """
    is_high, is_low = find_pivots(df, left, right)
    swings = _alternating_swings(df, is_high, is_low)
    breaks = _structure_breaks(df, swings, right)
    return {"swings": swings, "breaks": breaks}


def summary(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """Convenience: structure breaks as a tidy DataFrame (handy for inspection)."""
    res = analyze(df, left, right)
    return pd.DataFrame([asdict(b) for b in res["breaks"]])

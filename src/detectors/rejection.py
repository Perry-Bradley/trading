"""Rejection-candle (pin bar) detection — Lesson 9.

A rejection candle denies higher or lower prices, leaving a long wick on the
rejected side. The course notes that the *better* rejection candles also carry a
thicker body closing in the rejection direction (more authority than a classic
pin bar), so we score that as bonus strength rather than requiring a tiny body.

  * Bullish rejection (rejects lower prices): long LOWER wick, close in the
    upper part of the range. Strongest when it also closes bullish.
  * Bearish rejection (rejects higher prices): long UPPER wick, close in the
    lower part of the range. Strongest when it also closes bearish.
"""
from __future__ import annotations

import pandas as pd

from src.detectors.candles import anatomy


def detect(
    df: pd.DataFrame,
    wick_frac: float = 0.45,  # rejecting wick must be >= this fraction of the range
    body_max: float = 0.65,   # body no larger than this fraction (relaxed from 0.4 — real
                              # hammer/shooting-star candles often have a body up to 60%)
    close_part: float = 0.5,  # close must be in the favourable half of the range
) -> pd.DataFrame:
    """Return a frame indexed like df with columns:

        bull_rej, bear_rej  (bool)
        strength            (0..1-ish: rejecting-wick fraction, 0 if no rejection)
    """
    a = anatomy(df)
    h, l, c = df["high"], df["low"], df["close"]
    rng = (h - l).replace(0, pd.NA)
    close_pos = ((c - l) / rng).fillna(0.5)   # 0 = closed at low, 1 = closed at high

    bull = (
        (a["lower_frac"] >= wick_frac)
        & (a["body_frac"] <= body_max)
        & (close_pos >= close_part)
    )
    bear = (
        (a["upper_frac"] >= wick_frac)
        & (a["body_frac"] <= body_max)
        & (close_pos <= (1 - close_part))
    )

    out = pd.DataFrame(index=df.index)
    out["bull_rej"] = bull.fillna(False)
    out["bear_rej"] = bear.fillna(False)
    # strength: how dominant the rejecting wick is, with a bonus if the body
    # closes in the rejection direction.
    strength = pd.Series(0.0, index=df.index)
    strength = strength.where(~out["bull_rej"], a["lower_frac"] + 0.1 * a["is_bull"])
    strength = strength.where(~out["bear_rej"], a["upper_frac"] + 0.1 * (~a["is_bull"]))
    out["strength"] = strength.clip(0, 1.1).fillna(0.0)
    return out

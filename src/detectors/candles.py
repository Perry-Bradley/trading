"""Shared candle-anatomy helpers used by every detector.

All functions take an OHLC DataFrame (columns: open/high/low/close) and return
plain pandas Series / DataFrames so detectors can compose them freely.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def anatomy(df: pd.DataFrame) -> pd.DataFrame:
    """Per-candle body / wick / range features.

    Columns returned:
        rng         high - low (>0, guarded against flat bars)
        body        |close - open|
        upper_wick  high - max(open, close)
        lower_wick  min(open, close) - low
        is_bull     close >= open
        body_frac   body / rng
        upper_frac  upper_wick / rng
        lower_frac  lower_wick / rng
    """
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    rng = (h - l).replace(0, np.nan)
    body = (c - o).abs()
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    out = pd.DataFrame(index=df.index)
    out["rng"] = (h - l)
    out["body"] = body
    out["upper_wick"] = upper
    out["lower_wick"] = lower
    out["is_bull"] = c >= o
    out["body_frac"] = (body / rng).fillna(0.0)
    out["upper_frac"] = (upper / rng).fillna(0.0)
    out["lower_frac"] = (lower / rng).fillna(0.0)
    return out


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder-style simple rolling mean of true range)."""
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def is_displacement(df: pd.DataFrame, mult: float = 1.5, period: int = 14) -> pd.Series:
    """Boolean Series: candle body is an 'impulsive' move.

    A bar is displacement when its body exceeds `mult` x ATR — the strong,
    one-sided candle that creates order blocks / fair value gaps.
    """
    body = (df["close"] - df["open"]).abs()
    return body > (mult * atr(df, period))

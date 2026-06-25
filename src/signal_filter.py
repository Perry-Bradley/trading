"""Shared rules for which setups are still live (not stopped out / target hit)."""
from __future__ import annotations

import pandas as pd

# Max bars since signal for dashboard (strict) vs paper engine (wider, still active).
LIVE_MAX_AGE = {"H4": 8, "H1": 16, "M30": 24}
PAPER_MAX_AGE = {"H4": 32, "H1": 48, "M30": 64}


def is_active(s: dict, df: pd.DataFrame) -> bool:
    """True if price has NOT hit stop or target since the signal bar."""
    sig_time = pd.Timestamp(s["time"])
    after = df[df.index > sig_time]
    if after.empty:
        return True

    stop, target = s["stop"], s["target"]
    long = s["direction"] == "long"
    for _, row in after.iterrows():
        hi, lo = row["high"], row["low"]
        if long:
            if lo <= stop or hi >= target:
                return False
        else:
            if hi >= stop or lo <= target:
                return False
    return True


def is_live(s: dict, df: pd.DataFrame, tf: str) -> bool:
    """Active AND recent enough to show on the dashboard."""
    if s.get("age_bars", 999) > LIVE_MAX_AGE.get(tf, 8):
        return False
    return is_active(s, df)


def paper_eligible(s: dict, df: pd.DataFrame, tf: str) -> bool:
    """Paper engine: replay recent setups for learning (even if SL/TP already hit)."""
    _ = df  # kept for call-site compatibility
    return s.get("age_bars", 999) <= PAPER_MAX_AGE.get(tf, 32)

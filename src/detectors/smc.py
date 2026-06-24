"""Smart Money Concept detectors: Order Blocks, Fair Value Gaps, Liquidity Sweeps.

  * Order Block (Lesson 8): the last opposite-colour candle before an impulsive
    move that breaks structure. Bullish OB = last bearish candle before an up
    break (a demand zone); bearish OB = last bullish candle before a down break.
  * Fair Value Gap (Lesson 6): a 3-candle imbalance where candle 1 and candle 3
    don't overlap, leaving a price gap that price often returns to fill.
  * Liquidity Sweep (Lesson 7): price pokes beyond a prior swing high/low (grabs
    stops) but closes back inside — a stop hunt, not a real break.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.detectors.candles import is_displacement
from src.detectors.structure import analyze, find_pivots


@dataclass
class Zone:
    kind: str            # bullish/bearish (OB) or bullish/bearish (FVG)
    top: float
    bottom: float
    idx: int
    time: pd.Timestamp
    ref_idx: int | None = None       # the break (OB) or middle candle (FVG)
    mitigated_idx: int | None = None # first bar price returned into the zone


@dataclass
class Sweep:
    direction: str       # "bsl" (swept buy-side / highs) or "ssl" (swept lows)
    idx: int
    time: pd.Timestamp
    level: float         # the swing level that was swept


@dataclass
class Quasimodo:
    kind: str            # bullish / bearish
    idx: int             # bar of the confirming CHoCH
    time: pd.Timestamp
    sweep_level: float   # the liquidity that was grabbed (the "head")
    choch_level: float   # the structure level the move then broke (commitment)


def order_blocks(df: pd.DataFrame, left: int = 3, right: int = 3, lookback: int = 10, enforce_ote: bool = True) -> list[Zone]:
    """Order blocks anchored to structure breaks.
    If enforce_ote is True, the block must overlap with the Fib 0.62-0.79 OTE zone of the breaking impulse.
    """
    res = analyze(df, left, right)
    swings = res["swings"]
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    obs: list[Zone] = []
    for br in res["breaks"]:
        want_bullish_ob = br.direction == "up"     # up move -> last bearish candle
        lo = max(0, br.idx - lookback)
        ob_idx = None
        for j in range(br.idx - 1, lo - 1, -1):
            is_bear = c[j] < o[j]
            if want_bullish_ob and is_bear:
                ob_idx = j
                break
            if not want_bullish_ob and not is_bear:
                ob_idx = j
                break
        if ob_idx is None:
            continue
            
        top = float(df["high"].iat[ob_idx])
        bottom = float(df["low"].iat[ob_idx])
        
        if enforce_ote:
            # Find the origin of the impulse (last swing low for bullish break, last swing high for bearish)
            origin_swing = None
            for s in reversed(swings):
                if s.idx < br.idx and s.kind == ("L" if want_bullish_ob else "H"):
                    origin_swing = s
                    break
            
            if origin_swing is not None:
                impulse_start = origin_swing.price
                impulse_end = float(h[br.idx]) if want_bullish_ob else float(l[br.idx])
                range_len = impulse_end - impulse_start
                
                if want_bullish_ob:
                    ote_top = impulse_end - 0.62 * range_len
                    ote_bot = impulse_end - 0.79 * range_len
                    if top < ote_bot or bottom > ote_top:
                        continue # Not in OTE
                else:
                    ote_bot = impulse_end - 0.62 * range_len
                    ote_top = impulse_end - 0.79 * range_len
                    if bottom > ote_top or top < ote_bot:
                        continue # Not in OTE

        kind = "bullish" if want_bullish_ob else "bearish"
        obs.append(Zone(kind, top, bottom, ob_idx, df.index[ob_idx], ref_idx=br.idx))

    _mitigation(df, obs)
    return obs


def fair_value_gaps(df: pd.DataFrame, require_displacement: bool = True) -> list[Zone]:
    """3-candle fair value gaps."""
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    n = len(df)
    disp = is_displacement(df).to_numpy() if require_displacement else None
    fvgs: list[Zone] = []
    for i in range(1, n - 1):
        if disp is not None and not disp[i]:
            continue
        if h[i - 1] < l[i + 1]:               # bullish gap
            fvgs.append(Zone("bullish", float(l[i + 1]), float(h[i - 1]), i, df.index[i], ref_idx=i))
        elif l[i - 1] > h[i + 1]:             # bearish gap
            fvgs.append(Zone("bearish", float(l[i - 1]), float(h[i + 1]), i, df.index[i], ref_idx=i))
    _mitigation(df, fvgs)
    return fvgs


def liquidity_sweeps(df: pd.DataFrame, left: int = 3, right: int = 3) -> list[Sweep]:
    """Sweeps of the most recent confirmed swing high/low."""
    is_high, is_low = find_pivots(df, left, right)
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    n = len(df)

    # confirmation index -> level, walked causally
    sweeps: list[Sweep] = []
    last_sh = last_sl = None
    sh_iter = [(i, highs[i]) for i in range(n) if is_high[i]]
    sl_iter = [(i, lows[i]) for i in range(n) if is_low[i]]
    si = sj = 0
    for b in range(n):
        while si < len(sh_iter) and sh_iter[si][0] + right <= b:
            last_sh = sh_iter[si][1]; si += 1
        while sj < len(sl_iter) and sl_iter[sj][0] + right <= b:
            last_sl = sl_iter[sj][1]; sj += 1
        if last_sh is not None and highs[b] > last_sh and closes[b] < last_sh:
            sweeps.append(Sweep("bsl", b, df.index[b], float(last_sh)))
        if last_sl is not None and lows[b] < last_sl and closes[b] > last_sl:
            sweeps.append(Sweep("ssl", b, df.index[b], float(last_sl)))
    return sweeps


def breaker_blocks(df: pd.DataFrame, left: int = 3, right: int = 3, lookback: int = 10) -> list[Zone]:
    """Breaker blocks (Lesson 8): an order block that price BREAKS through and then
    RETESTS — it flips polarity and acts as the opposite zone.

    A bullish OB (demand) broken downward becomes resistance (a bearish breaker);
    a bearish OB (supply) broken upward becomes support (a bullish breaker).
    """
    obs = order_blocks(df, left, right, lookback)
    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    n = len(df)
    breakers: list[Zone] = []
    for ob in obs:
        violated = None
        for b in range(ob.idx + 1, n):
            if ob.kind == "bullish" and c[b] < ob.bottom:      # demand broken down
                violated = b; break
            if ob.kind == "bearish" and c[b] > ob.top:         # supply broken up
                violated = b; break
        if violated is None:
            continue
        retest = None
        for b in range(violated + 1, n):
            if h[b] >= ob.bottom and l[b] <= ob.top:
                retest = b; break
        flipped = "bearish" if ob.kind == "bullish" else "bullish"
        breakers.append(Zone(flipped, ob.top, ob.bottom, ob.idx, ob.time,
                             ref_idx=violated, mitigated_idx=retest))
    return breakers


def quasimodos(df: pd.DataFrame, left: int = 3, right: int = 3, window: int = 6) -> list[Quasimodo]:
    """Quasimodo / QML (Lesson 8 & 17): the premium reversal — a liquidity sweep
    (the 'head') immediately followed by a Change of Character against it.

    Bearish QM: buy-side liquidity swept (highs grabbed), then a CHoCH down.
    Bullish QM: sell-side liquidity swept (lows grabbed), then a CHoCH up.
    These align with the OB→Breaker→QML idea and are the method's highest-conviction
    reversal points when they also agree with HTF bias.
    """
    sweeps = liquidity_sweeps(df, left, right)
    chochs = [b for b in analyze(df, left, right)["breaks"] if b.kind == "CHoCH"]
    out: list[Quasimodo] = []
    for ch in chochs:
        want = "bsl" if ch.direction == "down" else "ssl"   # opposite-side grab before the flip
        sw = next((s for s in sweeps if s.direction == want and 0 <= ch.idx - s.idx <= window), None)
        if sw is None:
            continue
        out.append(Quasimodo("bearish" if ch.direction == "down" else "bullish",
                             ch.idx, ch.time, sw.level, ch.level))
    return out


@dataclass
class AMD:
    direction: str       # "bullish" or "bearish" distribution
    idx: int
    time: pd.Timestamp
    accumulation_high: float
    accumulation_low: float
    manipulation_extreme: float

def amd_cycles(df: pd.DataFrame, session_start_hour: int = 0, session_len: int = 8) -> list[AMD]:
    """AMD (Accumulation, Manipulation, Distribution) / Judas Swing detection.
    Typically Accumulation is Asian session (e.g., 00:00 to 08:00 UTC).
    Manipulation (Judas Swing) sweeps accumulation highs/lows at London/NY open.
    Distribution is the true trend.
    """
    out: list[AMD] = []
    times = pd.Series(df.index)
    
    # We define accumulation as period from session_start_hour for session_len hours
    in_acc = (times.dt.hour >= session_start_hour) & (times.dt.hour < session_start_hour + session_len)
    
    # Group by date to find daily cycles
    dates = times.dt.date.unique()
    for d in dates:
        day_df = df[times.dt.date == d]
        day_times = times[times.dt.date == d]
        acc_mask = (day_times.dt.hour >= session_start_hour) & (day_times.dt.hour < session_start_hour + session_len)
        if acc_mask.sum() == 0:
            continue
            
        acc_df = day_df[acc_mask.values]
        acc_high = acc_df['high'].max()
        acc_low = acc_df['low'].min()
        
        post_acc_mask = (day_times.dt.hour >= session_start_hour + session_len)
        if post_acc_mask.sum() == 0:
            continue
            
        post_acc_df = day_df[post_acc_mask.values]
        post_high = post_acc_df['high'].max()
        post_low = post_acc_df['low'].min()
        
        # Did we manipulate above acc_high then distribute below acc_low? (Bearish AMD)
        if post_high > acc_high and post_acc_df['close'].min() < acc_low:
            # Find the index of the breakdown
            break_idx = post_acc_df[post_acc_df['close'] < acc_low].index[0]
            global_idx = df.index.get_loc(break_idx)
            out.append(AMD("bearish", global_idx, break_idx, acc_high, acc_low, post_high))
            
        # Did we manipulate below acc_low then distribute above acc_high? (Bullish AMD)
        elif post_low < acc_low and post_acc_df['close'].max() > acc_high:
            break_idx = post_acc_df[post_acc_df['close'] > acc_high].index[0]
            global_idx = df.index.get_loc(break_idx)
            out.append(AMD("bullish", global_idx, break_idx, acc_high, acc_low, post_low))
            
    return out


def _mitigation(df: pd.DataFrame, zones: list[Zone]) -> None:
    """Mark the first bar after creation where price re-enters each zone."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    for z in zones:
        for b in range(z.idx + 1, n):
            if highs[b] >= z.bottom and lows[b] <= z.top:
                z.mitigated_idx = b
                break

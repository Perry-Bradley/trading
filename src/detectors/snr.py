"""Malaysian Support & Resistance (MSNR) zone detection — Lesson 9.

Rules from the course:
  * SNR levels are drawn from CLOSE -> OPEN of the candle pair at a turn,
    ignoring wicks.
      - Resistance ('A' shape): bullish candle's close -> next bearish candle's
        open, at a swing high.
      - Support ('V' shape): bearish candle's close -> next bullish candle's
        open, at a swing low.
  * Fresh vs unfresh: a level is *fresh* until price (wick or body) touches it;
    after a touch it becomes *unfresh* (weaker).
  * Flip (SBR / RBS): if a later candle *closes through* the level with its
    body, the level flips role — Support Becomes Resistance, or vice versa.

Each zone is anchored at a structural swing (so we get meaningful levels, not a
zone at every candle), then we walk forward to fill in touch / flip state.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.detectors.candles import atr
from src.detectors.structure import find_pivots


@dataclass
class SNRZone:
    kind: str             # "resistance" or "support" (original role)
    top: float            # upper bound of the close->open zone
    bottom: float         # lower bound
    anchor_idx: int       # bar where the zone is established (the turn)
    anchor_time: pd.Timestamp
    first_touch_idx: int | None = None   # first bar to touch the zone with a WICK (the tap)
    invalidated_idx: int | None = None   # first bar whose BODY entered the zone (kills it)
    flipped: bool = False                # did price close fully through it?
    flip_idx: int | None = None
    flipped_kind: str | None = None      # role after flip

    def is_fresh_at(self, idx: int) -> bool:
        """Fresh = established, and not yet touched (wick or body) as of bar `idx`.

        MSNR: a fresh level is untouched snow. The first wick tap is the trade;
        after that it is unfresh.
        """
        if idx <= self.anchor_idx:
            return False
        return self.first_touch_idx is None or self.first_touch_idx >= idx

    def is_valid_at(self, idx: int) -> bool:
        """Valid = no candle BODY has closed into/through the zone before `idx`.

        MSNR: 'a body touch is never accepted'. A wick tap leaves the level a
        clean reaction zone; a body violation invalidates it.
        """
        if idx <= self.anchor_idx:
            return False
        return self.invalidated_idx is None or self.invalidated_idx >= idx

    def mid(self) -> float:
        return (self.top + self.bottom) / 2.0


def _zone_at_high(o, c, p: int, n: int) -> tuple[float, float] | None:
    """Resistance close->open zone around a swing high at bar p."""
    # Prefer the bull->bear turn straddling the peak.
    if c[p] >= o[p] and p + 1 < n:          # peak candle bullish -> next is the turn
        a, b = p, p + 1
    elif p - 1 >= 0:                        # peak candle bearish -> turn was before it
        a, b = p - 1, p
    else:
        return None
    top = max(c[a], o[b])
    bottom = min(c[a], o[b])
    if top == bottom:                       # degenerate (doji-ish) — give it a hair of width
        return None
    return top, bottom


def _zone_at_low(o, c, p: int, n: int) -> tuple[float, float] | None:
    """Support close->open zone around a swing low at bar p."""
    if c[p] < o[p] and p + 1 < n:           # trough candle bearish -> next is the turn
        a, b = p, p + 1
    elif p - 1 >= 0:
        a, b = p - 1, p
    else:
        return None
    top = max(c[a], o[b])
    bottom = min(c[a], o[b])
    if top == bottom:
        return None
    return top, bottom


def _resolve_state(df: pd.DataFrame, zone: SNRZone, right: int) -> None:
    """Walk forward from the anchor to fill touch / flip state (causal-ish:
    we only look at bars strictly after the zone is confirmed)."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    start = zone.anchor_idx + right + 1     # zone is only 'known' after confirmation lag
    n = len(df)
    for b in range(start, n):
        # touch = wick or body enters the zone band (first interaction = the tap)
        if zone.first_touch_idx is None and highs[b] >= zone.bottom and lows[b] <= zone.top:
            zone.first_touch_idx = b
        # invalidation = candle BODY (open..close) enters the zone band
        if zone.invalidated_idx is None:
            body_hi, body_lo = max(opens[b], closes[b]), min(opens[b], closes[b])
            if body_hi >= zone.bottom and body_lo <= zone.top:
                zone.invalidated_idx = b
        # flip = body close fully through the level
        if not zone.flipped:
            if zone.kind == "resistance" and closes[b] > zone.top:
                zone.flipped, zone.flip_idx, zone.flipped_kind = True, b, "support"
            elif zone.kind == "support" and closes[b] < zone.bottom:
                zone.flipped, zone.flip_idx, zone.flipped_kind = True, b, "resistance"


def _pad(top: float, bottom: float, min_half_width: float) -> tuple[float, float]:
    """Ensure the zone is at least `2 * min_half_width` wide (centred)."""
    center = (top + bottom) / 2.0
    half = max((top - bottom) / 2.0, min_half_width)
    return center + half, center - half


def detect(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
    buffer_atr: float = 0.25,   # min zone half-width as a fraction of ATR
) -> list[SNRZone]:
    """Detect all SNR zones in an OHLC frame.

    The raw close->open junction is often near-zero width, so each zone is
    padded to a minimum half-width of `buffer_atr * ATR` at the anchor bar —
    turning a hairline level into a realistic reaction band.
    """
    is_high, is_low = find_pivots(df, left, right)
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    atr_arr = atr(df).to_numpy()
    n = len(df)
    zones: list[SNRZone] = []

    for p in range(n):
        anchor = min(p + 1, n - 1)
        half = buffer_atr * atr_arr[anchor]
        if is_high[p]:
            z = _zone_at_high(o, c, p, n)
            if z:
                top, bottom = _pad(*z, half)
                zones.append(SNRZone("resistance", top, bottom, anchor, df.index[anchor]))
        if is_low[p]:
            z = _zone_at_low(o, c, p, n)
            if z:
                top, bottom = _pad(*z, half)
                zones.append(SNRZone("support", top, bottom, anchor, df.index[anchor]))

    for z in zones:
        _resolve_state(df, z, right)
    return zones


def fresh_zones_at(zones: list[SNRZone], idx: int) -> list[SNRZone]:
    """Subset of zones that are fresh (untouched) as of bar `idx`."""
    return [z for z in zones if z.is_fresh_at(idx)]

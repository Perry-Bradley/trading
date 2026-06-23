"""MSNR setup scanner (Phase 2).

Combines the Phase-1 detectors into the MSNR playbook from Lesson 9:

    1. HTF storyline / bias       -> market structure on the higher timeframe
    2. Price at a FRESH SNR level aligned with that bias
    3. Multi-timeframe alignment  -> the HTF zone overlaps a fresh LTF zone
       (Lesson 9 ladder: Daily<->H4, H4<->H1, H1<->M30)
    4. Confirmation on the LTF    -> rejection candle, a CHoCH in the bias
       direction, and/or a recent liquidity sweep

Bias-alignment and a fresh SNR are REQUIRED; the rest add to a confluence score.
This scans the *current* state (the latest bar) — "where are setups right now".
Historical scanning for backtests is Phase 3.

Usage:
    python -m src.scanner                       # all pairs, H4 bias / H1 entry
    python -m src.scanner --htf D1 --ltf H4
    python -m src.scanner --pair BTCUSD --htf H4 --ltf H1
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import config
from src.data.fetch import load
from src.detectors import rejection, smc, snr
from src.detectors.candles import atr
from src.detectors.structure import analyze

# Which lower timeframe pairs with each higher timeframe (MSNR ladder).
LADDER = {"D1": "H4", "H4": "H1", "H1": "M30"}

# Confluence weights for the score (bias + fresh SNR are required, not scored).
WEIGHTS = {"mtf_aligned": 1.0, "rejection": 1.0, "choch": 1.0, "sweep": 0.5}


@dataclass
class Setup:
    pair: str
    direction: str            # "long" or "short"
    htf: str
    ltf: str
    zone_low: float
    zone_high: float
    entry: float
    stop: float
    target: float
    rr: float
    confluences: dict = field(default_factory=dict)
    score: float = 0.0

    def summary(self) -> str:
        on = [k for k, v in self.confluences.items() if v]
        return (
            f"{self.pair:7} {self.direction.upper():5} {self.htf}->{self.ltf}  "
            f"zone [{self.zone_low:.5f}, {self.zone_high:.5f}]  "
            f"entry {self.entry:.5f} SL {self.stop:.5f} TP {self.target:.5f}  "
            f"R:R 1:{self.rr:.1f}  score {self.score:.1f}  [{', '.join(on)}]"
        )


def _bias(df) -> int:
    """+1 bullish / -1 bearish / 0 unknown, from the last structure break."""
    breaks = analyze(df)["breaks"]
    if not breaks:
        return 0
    return 1 if breaks[-1].direction == "up" else -1


def _overlaps(a_lo, a_hi, b_lo, b_hi) -> bool:
    return a_lo <= b_hi and b_lo <= a_hi


def scan_pair(
    pair: str,
    htf: str = "H4",
    ltf: str = "H1",
    near_atr: float = 0.6,    # how close price must be to the zone to be "at" it
    rr_target: float = 3.0,   # MSNR aims high R:R
    confirm_bars: int = 6,    # LTF lookback window for confirmation signals
) -> list[Setup]:
    htf_df = load(pair, htf)
    ltf_df = load(pair, ltf)

    bias = _bias(htf_df)
    if bias == 0:
        return []

    htf_zones = snr.detect(htf_df)
    last_idx = len(htf_df) - 1
    last_close = float(htf_df["close"].iat[-1])
    a = float(atr(htf_df).iat[-1])
    pad = near_atr * a

    want = "support" if bias > 0 else "resistance"
    # MSNR: trade fresh AND valid (no body has closed into the level) zones only.
    fresh = [z for z in htf_zones
             if z.kind == want and z.is_fresh_at(last_idx) and z.is_valid_at(last_idx)]
    # zone price is currently interacting with (within the band + a near buffer)
    active = [z for z in fresh if (z.bottom - pad) <= last_close <= (z.top + pad)]
    if not active:
        return []

    # LTF context for confirmation
    ltf_zones = snr.detect(ltf_df)
    ltf_fresh = snr.fresh_zones_at(ltf_zones, len(ltf_df) - 1)
    rej = rejection.detect(ltf_df).tail(confirm_bars)
    ltf_breaks = [b for b in analyze(ltf_df)["breaks"] if b.idx >= len(ltf_df) - confirm_bars]
    ltf_sweeps = [s for s in smc.liquidity_sweeps(ltf_df) if s.idx >= len(ltf_df) - confirm_bars]

    setups: list[Setup] = []
    for z in active:
        mtf = any(zz.kind == want and _overlaps(z.bottom, z.top, zz.bottom, zz.top) for zz in ltf_fresh)
        if bias > 0:
            rej_ok = bool(rej["bull_rej"].any())
            choch_ok = any(b.direction == "up" and b.kind == "CHoCH" for b in ltf_breaks)
            sweep_ok = any(s.direction == "ssl" for s in ltf_sweeps)
        else:
            rej_ok = bool(rej["bear_rej"].any())
            choch_ok = any(b.direction == "down" and b.kind == "CHoCH" for b in ltf_breaks)
            sweep_ok = any(s.direction == "bsl" for s in ltf_sweeps)

        conf = {"mtf_aligned": mtf, "rejection": rej_ok, "choch": choch_ok, "sweep": sweep_ok}
        score = sum(WEIGHTS[k] for k, v in conf.items() if v)

        # X-Factor ("no validation, no trade"): bias + a fresh level is not enough —
        # require at least one confirmation trigger (a rejection candle or an LTF CHoCH).
        if not (rej_ok or choch_ok):
            continue

        sl_pad = 0.1 * a
        if bias > 0:
            entry = min(last_close, z.top)
            stop = z.bottom - sl_pad
            risk = max(entry - stop, 1e-9)
            target = entry + rr_target * risk
        else:
            entry = max(last_close, z.bottom)
            stop = z.top + sl_pad
            risk = max(stop - entry, 1e-9)
            target = entry - rr_target * risk

        setups.append(Setup(
            pair, "long" if bias > 0 else "short", htf, ltf,
            z.bottom, z.top, entry, stop, target, rr_target, conf, score,
        ))

    setups.sort(key=lambda s: s.score, reverse=True)
    return setups


def scan_all(htf: str = "H4", ltf: str = "H1", min_score: float = 0.0) -> list[Setup]:
    out: list[Setup] = []
    for pair in config.PAIRS:
        try:
            out.extend(s for s in scan_pair(pair, htf, ltf) if s.score >= min_score)
        except FileNotFoundError as e:
            print(f"  (skip {pair}: {e})")
    out.sort(key=lambda s: s.score, reverse=True)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Scan for live MSNR setups.")
    p.add_argument("--pair", choices=list(config.YF_TICKERS))
    p.add_argument("--htf", default="H4", choices=list(config.TIMEFRAMES))
    p.add_argument("--ltf", default="H1", choices=list(config.TIMEFRAMES))
    p.add_argument("--min-score", type=float, default=0.0)
    args = p.parse_args(argv)

    print(f"Scanning {'all pairs' if not args.pair else args.pair} | bias={args.htf} entry={args.ltf}\n")
    setups = (scan_pair(args.pair, args.htf, args.ltf) if args.pair
              else scan_all(args.htf, args.ltf, args.min_score))
    setups = [s for s in setups if s.score >= args.min_score]
    if not setups:
        print("No live setups matching the criteria right now.")
        return 0
    for s in setups:
        print("  " + s.summary())
    print(f"\n{len(setups)} setup(s). (bias + fresh SNR required; score = optional confluences)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

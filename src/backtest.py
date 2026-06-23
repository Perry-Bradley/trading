"""Phase 3 — causal MSNR backtester (the truth-teller).

Design priorities, straight from the course's risk modules (05 & 15):
  * Honesty: results are in R-multiples, and realistic transaction costs
    (spread + slippage) are subtracted from every trade. A strategy that looks
    good gross can be a net loser after costs.
  * Causality: nothing uses future information. Swings/zones carry confirmation
    lag, structure breaks confirm on close, and a zone's "freshness as of bar t"
    is decided only by whether it was touched *before* t (which the future cannot
    change). Entries fill at the NEXT bar's open.
  * Conservatism: if a bar could hit both stop and target, we assume the STOP
    filled first.

The model (one faithful slice of MSNR — single entry timeframe + HTF bias):
  1. Bias from the higher timeframe's structure (last confirmed break) mapped
     causally onto each entry-timeframe bar.
  2. A fresh, valid SNR zone on the entry timeframe, aligned with that bias
     (support in an uptrend, resistance in a downtrend).
  3. Trigger: price taps the zone AND prints a rejection candle in the bias
     direction (the confirmation candle). Enter next bar's open.
  4. Stop just beyond the zone (ATR buffer); target at a fixed R multiple.

Usage:
    python -m src.backtest                          # all pairs, H4 entry / D1 bias
    python -m src.backtest --pair EURUSD --tf H4 --bias-tf D1 --target-r 3
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from src.data.fetch import load
from src.detectors import rejection, smc, snr
from src.detectors.candles import atr
from src.detectors.structure import analyze

# Round-trip transaction cost (spread + slippage) in "pips" (price = pips * pip_size).
DEFAULT_COST_PIPS = {
    "EURUSD": 1.2, "GBPUSD": 1.5, "AUDUSD": 1.5,
    "EURNZD": 3.0, "CHFJPY": 2.0, "BTCUSD": 25.0,
}


@dataclass
class Trade:
    pair: str
    direction: str          # long / short
    entry_time: pd.Timestamp
    entry: float
    stop: float
    target: float
    exit_time: pd.Timestamp
    exit: float
    outcome: str            # win / loss / timeout
    r: float                # realised R, net of cost
    features: dict = field(default_factory=dict)   # causal features known at entry


def _htf_bias_array(entry_df: pd.DataFrame, htf_df: pd.DataFrame) -> np.ndarray:
    """+1/-1/0 bias for each entry-TF bar, from the last HTF structure break
    whose time is <= that bar's time (causal as-of join)."""
    breaks = analyze(htf_df)["breaks"]
    out = np.zeros(len(entry_df), dtype=int)
    if not breaks:
        return out
    btimes = np.array([b.time.value for b in breaks])
    bdir = np.array([1 if b.direction == "up" else -1 for b in breaks])
    etimes = entry_df.index.values.astype("datetime64[ns]").astype(np.int64)
    pos = np.searchsorted(btimes, etimes, side="right") - 1
    valid = pos >= 0
    out[valid] = bdir[pos[valid]]
    return out


def _build_feature_context(df: pd.DataFrame, atr_arr, left, right) -> dict:
    """Precompute the extra detectors needed for per-trade features (once/pair)."""
    breaks = analyze(df, left, right)["breaks"]
    chochs = [(b.idx, 1 if b.direction == "up" else -1) for b in breaks if b.kind == "CHoCH"]
    return {
        "chochs": chochs,
        "sweeps": smc.liquidity_sweeps(df, left, right),
        "obs": smc.order_blocks(df, left, right),
        "fvgs": smc.fair_value_gaps(df),
        "atr_med": pd.Series(atr_arr).rolling(100, min_periods=20).median().to_numpy(),
    }


def _features(ctx, df, i, bias, zone, atr_i, rej_strength, K=10) -> dict:
    """Causal features known at the trigger bar i (uses only data with idx <= i)."""
    h = df["high"].to_numpy(); l = df["low"].to_numpy()
    # recent aligned CHoCH (entry-TF structure) and trend maturity
    choch_recent = any(idx <= i and idx >= i - K and d == bias for idx, d in ctx["chochs"])
    last_choch = max((idx for idx, _ in ctx["chochs"] if idx <= i), default=i)
    trend_age = i - last_choch
    # recent aligned liquidity sweep (ssl feeds longs, bsl feeds shorts)
    want_sweep = "ssl" if bias > 0 else "bsl"
    sweep_recent = any(i - K <= s.idx <= i and s.direction == want_sweep for s in ctx["sweeps"])
    # order block / FVG confluence overlapping the SNR zone, created on/before i
    want_zone = "bullish" if bias > 0 else "bearish"
    ob_conf = any(ob.idx <= i and ob.kind == want_zone
                  and ob.bottom <= zone.top and zone.bottom <= ob.top for ob in ctx["obs"])
    fvg_conf = any(f.idx <= i and f.kind == want_zone
                   and f.bottom <= zone.top and zone.bottom <= f.top for f in ctx["fvgs"])
    # depth of the rejecting wick into the zone, in ATR
    if bias > 0:
        depth = (zone.top - l[i]) / atr_i
    else:
        depth = (h[i] - zone.bottom) / atr_i
    atr_med = ctx["atr_med"][i]
    t = df.index[i]
    return {
        "rej_strength": float(rej_strength),
        "zone_width_atr": float((zone.top - zone.bottom) / atr_i),
        "zone_age": float(i - zone.anchor_idx),
        "depth_atr": float(depth),
        "atr_regime": float(atr_i / atr_med) if atr_med and atr_med > 0 else 1.0,
        "choch_recent": int(choch_recent),
        "sweep_recent": int(sweep_recent),
        "ob_conf": int(ob_conf),
        "fvg_conf": int(fvg_conf),
        "trend_age": float(min(trend_age, 200)),
        "hour": float(t.hour),
        "dow": float(t.dayofweek),
    }


def run(
    pair: str,
    tf: str = "H4",
    bias_tf: str | None = "D1",
    target_r: float = 3.0,
    sl_buffer_atr: float = 0.25,
    max_hold: int = 60,
    cost_pips: float | None = None,
    left: int = 3,
    right: int = 3,
    collect_features: bool = False,
) -> dict:
    df = load(pair, tf)
    o = df["open"].to_numpy(); h = df["high"].to_numpy()
    l = df["low"].to_numpy();  c = df["close"].to_numpy()
    times = df.index
    n = len(df)

    atr_arr = atr(df).to_numpy()
    zones = snr.detect(df, left, right)
    rej = rejection.detect(df)
    bull_rej = rej["bull_rej"].to_numpy()
    bear_rej = rej["bear_rej"].to_numpy()
    rej_strength = rej["strength"].to_numpy()
    ctx = _build_feature_context(df, atr_arr, left, right) if collect_features else None

    if bias_tf:
        bias = _htf_bias_array(df, load(pair, bias_tf))
    else:
        bias = _htf_bias_array(df, df)   # same-timeframe bias from structure

    # index zones by their tap bar for O(1) lookup
    taps: dict[int, list] = {}
    for z in zones:
        if z.first_touch_idx is not None:
            taps.setdefault(z.first_touch_idx, []).append(z)

    pip = config.pip_size(pair)
    cost_pips = DEFAULT_COST_PIPS.get(pair, 1.5) if cost_pips is None else cost_pips
    cost_price = cost_pips * pip

    trades: list[Trade] = []
    i = 0
    while i < n - 1:
        b = bias[i]
        z_here = taps.get(i)
        if b == 0 or not z_here:
            i += 1
            continue

        want = "support" if b > 0 else "resistance"
        trigger = bull_rej[i] if b > 0 else bear_rej[i]
        # pick an aligned, valid zone tapped at this bar with the right rejection
        zone = next((z for z in z_here
                     if z.kind == want and z.is_valid_at(i) and trigger), None)
        if zone is None:
            i += 1
            continue

        # enter next bar open
        e_idx = i + 1
        entry = o[e_idx]
        a = atr_arr[i] if atr_arr[i] > 0 else (h[i] - l[i])
        if b > 0:
            stop = zone.bottom - sl_buffer_atr * a
            risk = entry - stop
        else:
            stop = zone.top + sl_buffer_atr * a
            risk = stop - entry
        if risk <= 0:
            i += 1
            continue
        target = entry + target_r * risk if b > 0 else entry - target_r * risk
        cost_r = cost_price / risk

        # simulate forward
        outcome, exit_price, exit_idx = "timeout", c[min(e_idx + max_hold, n - 1)], min(e_idx + max_hold, n - 1)
        for j in range(e_idx, min(e_idx + max_hold, n)):
            if b > 0:
                if l[j] <= stop:                      # stop checked first (conservative)
                    outcome, exit_price, exit_idx = "loss", stop, j; break
                if h[j] >= target:
                    outcome, exit_price, exit_idx = "win", target, j; break
            else:
                if h[j] >= stop:
                    outcome, exit_price, exit_idx = "loss", stop, j; break
                if l[j] <= target:
                    outcome, exit_price, exit_idx = "win", target, j; break

        gross_r = ((exit_price - entry) if b > 0 else (entry - exit_price)) / risk
        r = gross_r - cost_r
        feats = _features(ctx, df, i, b, zone, atr_arr[i], rej_strength[i]) if ctx else {}
        trades.append(Trade(pair, "long" if b > 0 else "short", times[e_idx], entry,
                            stop, target, times[exit_idx], exit_price, outcome, r, feats))
        i = exit_idx + 1     # one position at a time; resume after the exit

    return _metrics(pair, tf, bias_tf, target_r, trades)


def signals(pair: str, tf: str = "H4", bias_tf: str = "D1", target_r: float = 2.0,
            lookback: int = 3, sl_buffer_atr: float = 0.25, left: int = 3,
            right: int = 3) -> list[dict]:
    """Detect setups that triggered in the last `lookback` bars (for live use).

    Same trigger logic as run(), but WITHOUT trade simulation / one-position
    skipping — it reports every fresh trigger near the right edge, each with the
    same causal feature vector the ML model was trained on, plus entry/SL/TP.
    """
    df = load(pair, tf)
    h = df["high"].to_numpy(); l = df["low"].to_numpy(); c = df["close"].to_numpy()
    n = len(df)
    atr_arr = atr(df).to_numpy()
    zones = snr.detect(df, left, right)
    rej = rejection.detect(df)
    bull_rej = rej["bull_rej"].to_numpy(); bear_rej = rej["bear_rej"].to_numpy()
    rej_strength = rej["strength"].to_numpy()
    bias = _htf_bias_array(df, load(pair, bias_tf)) if bias_tf else _htf_bias_array(df, df)
    ctx = _build_feature_context(df, atr_arr, left, right)

    taps: dict[int, list] = {}
    for z in zones:
        if z.first_touch_idx is not None:
            taps.setdefault(z.first_touch_idx, []).append(z)

    out = []
    for i in range(max(0, n - lookback), n):
        b = bias[i]
        if b == 0 or i not in taps:
            continue
        want = "support" if b > 0 else "resistance"
        trig = bull_rej[i] if b > 0 else bear_rej[i]
        zone = next((z for z in taps[i] if z.kind == want and z.is_valid_at(i) and trig), None)
        if zone is None:
            continue
        a = atr_arr[i] if atr_arr[i] > 0 else (h[i] - l[i])
        entry = c[i]
        if b > 0:
            stop = zone.bottom - sl_buffer_atr * a
            risk = entry - stop
            target = entry + target_r * risk
        else:
            stop = zone.top + sl_buffer_atr * a
            risk = stop - entry
            target = entry - target_r * risk
        if risk <= 0:
            continue
        feats = _features(ctx, df, i, b, zone, a, rej_strength[i])
        feats["direction"] = 1 if b > 0 else 0           # match dataset feature set
        feats["tf_minutes"] = {"M30": 30, "H1": 60, "H4": 240, "D1": 1440}[tf]
        out.append({
            "pair": pair, "tf": tf, "bias_tf": bias_tf,
            "time": df.index[i], "direction": "long" if b > 0 else "short",
            "entry": entry, "stop": stop, "target": target, "rr": target_r,
            "features": feats,
        })
    return out


def overview(pair: str, tf: str = "H4", bias_tf: str = "D1", target_r: float = 2.0) -> dict:
    """Lightweight per-pair snapshot for the dashboard pairs panel."""
    df = load(pair, tf)
    barr = _htf_bias_array(df, load(pair, bias_tf)) if bias_tf else _htf_bias_array(df, df)
    b = int(barr[-1]) if len(barr) else 0
    has_sig = len(signals(pair, tf, bias_tf, target_r, lookback=3)) > 0
    return {
        "pair": pair,
        "bias": "long" if b > 0 else "short" if b < 0 else "flat",
        "price": float(df["close"].iat[-1]),
        "signal": has_sig,
    }


def _metrics(pair, tf, bias_tf, target_r, trades: list[Trade]) -> dict:
    rs = np.array([t.r for t in trades])
    wins = [t for t in trades if t.outcome == "win"]
    losses = [t for t in trades if t.outcome == "loss"]
    n = len(trades)
    gross_win = sum(t.r for t in trades if t.r > 0)
    gross_loss = -sum(t.r for t in trades if t.r < 0)

    equity = np.cumsum(rs) if n else np.array([0.0])
    peak = np.maximum.accumulate(equity) if n else np.array([0.0])
    max_dd = float((peak - equity).max()) if n else 0.0

    return {
        "pair": pair, "tf": tf, "bias_tf": bias_tf, "target_r": target_r,
        "trades": n,
        "wins": len(wins), "losses": len(losses),
        "timeouts": sum(1 for t in trades if t.outcome == "timeout"),
        "win_rate": (len(wins) / n) if n else 0.0,
        "breakeven_wr": 1.0 / (1.0 + target_r),
        "expectancy_r": float(rs.mean()) if n else 0.0,
        "total_r": float(rs.sum()) if n else 0.0,
        "avg_win_r": float(np.mean([t.r for t in wins])) if wins else 0.0,
        "avg_loss_r": float(np.mean([t.r for t in losses])) if losses else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
        "max_dd_r": max_dd,
        "_trades": trades,
    }


def _fmt(m: dict) -> str:
    pf = "inf" if m["profit_factor"] == float("inf") else f"{m['profit_factor']:.2f}"
    return (f"{m['pair']:7} {m['tf']}/{m['bias_tf']}  trades {m['trades']:>4}  "
            f"win {m['win_rate']*100:5.1f}% (be {m['breakeven_wr']*100:4.1f}%)  "
            f"exp {m['expectancy_r']:+.3f}R  total {m['total_r']:+7.1f}R  "
            f"PF {pf:>4}  maxDD {m['max_dd_r']:5.1f}R")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Backtest the MSNR model.")
    p.add_argument("--pair", choices=list(config.YF_TICKERS))
    p.add_argument("--tf", default="H4", choices=list(config.TIMEFRAMES))
    p.add_argument("--bias-tf", default="D1", choices=list(config.TIMEFRAMES))
    p.add_argument("--target-r", type=float, default=3.0)
    p.add_argument("--sl-buffer-atr", type=float, default=0.25)
    p.add_argument("--max-hold", type=int, default=60)
    args = p.parse_args(argv)

    pairs = [args.pair] if args.pair else config.PAIRS
    print(f"Backtest  entry={args.tf}  bias={args.bias_tf}  target={args.target_r}R  "
          f"(costs ON, SL-first, causal)\n")
    agg = []
    for pr in pairs:
        try:
            m = run(pr, args.tf, args.bias_tf, args.target_r, args.sl_buffer_atr, args.max_hold)
            agg.append(m)
            print("  " + _fmt(m))
        except FileNotFoundError as e:
            print(f"  (skip {pr}: {e})")

    if len(agg) > 1:
        tot = sum(m["total_r"] for m in agg)
        tr = sum(m["trades"] for m in agg)
        w = sum(m["wins"] for m in agg)
        print("\n  " + "-" * 70)
        print(f"  PORTFOLIO: {tr} trades, win {100*w/tr:.1f}%, total {tot:+.1f}R "
              f"(~{tot*1:.1f}% at 1% risk/trade, before compounding)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

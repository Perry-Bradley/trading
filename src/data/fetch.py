"""Download and cache OHLCV from live sources.

Routing:
  BTCUSD     -> Binance (real-time, no key)
  V100, V25  -> Deriv WebSocket
  Forex/XAU  -> Twelve Data (requires TWELVEDATA_KEY)

Data is saved as parquet under data/<PAIR>_<TIMEFRAME>.parquet.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

import config


def load(pair: str, timeframe: str) -> pd.DataFrame:
    """Load a previously-fetched OHLCV frame from disk."""
    path = config.DATA_DIR / f"{pair}_{timeframe}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — fetch it first: python -m src.data.fetch --pair {pair}"
        )
    return pd.read_parquet(path)


def _sanitize(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce OHLC integrity on incoming bars."""
    df = df.copy()
    hi_need = df[["open", "close"]].max(axis=1)
    lo_need = df[["open", "close"]].min(axis=1)
    bad = (df["high"] < hi_need) | (df["low"] > lo_need)
    n_bad = int(bad.sum())
    if n_bad:
        df["high"] = df[["high"]].join(hi_need.rename("_h")).max(axis=1)
        df["low"] = df[["low"]].join(lo_need.rename("_l")).min(axis=1)
        print(f"    (sanitized {n_bad} bar(s) with OHLC integrity issues)")
    return df


def source_for(pair: str) -> str:
    """Which live source handles this pair."""
    if pair in config.CRYPTO:
        return "binance"
    if pair in ("V100", "V25"):
        return "deriv"
    return "twelvedata"


def fetch(pair: str, timeframe: str) -> pd.DataFrame:
    """Route to the live source for this instrument. No yfinance fallback."""
    if pair not in config.PAIRS:
        raise ValueError(f"Unknown pair {pair!r}. Known: {list(config.PAIRS)}")
    if timeframe not in config.TIMEFRAMES:
        raise ValueError(f"Unknown timeframe {timeframe!r}. Known: {list(config.TIMEFRAMES)}")

    if pair in config.CRYPTO:
        from src.data.sources import binance
        return _sanitize(binance.fetch_ohlcv(pair, timeframe))
    if pair in ("V100", "V25"):
        from src.data.sources import deriv_data
        return _sanitize(deriv_data.fetch_ohlcv(pair, timeframe))

    from src.data.sources import twelvedata
    return _sanitize(twelvedata.fetch_ohlcv(pair, timeframe))


def save(pair: str, timeframe: str) -> pd.DataFrame:
    df = fetch(pair, timeframe)
    out = config.DATA_DIR / f"{pair}_{timeframe}.parquet"
    df.to_parquet(out)
    span = f"{df.index.min()} -> {df.index.max()}"
    print(f"  saved {pair} {timeframe:>3}: {len(df):>6} bars  ({span})  -> {out.name}")
    return df


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch OHLCV from live sources.")
    p.add_argument("--pair", choices=list(config.PAIRS), help="Single pair to fetch.")
    p.add_argument("--timeframe", choices=list(config.TIMEFRAMES), help="Single timeframe.")
    p.add_argument("--all", action="store_true", help="Fetch every pair and timeframe.")
    args = p.parse_args(argv)

    if args.all:
        pairs, tfs = config.PAIRS, list(config.TIMEFRAMES)
    elif args.pair and args.timeframe:
        pairs, tfs = [args.pair], [args.timeframe]
    elif args.pair:
        pairs, tfs = [args.pair], list(config.TIMEFRAMES)
    else:
        p.error("provide --all, or --pair (optionally with --timeframe)")

    print(f"Fetching {len(pairs)} pair(s) x {len(tfs)} timeframe(s)...")
    failures = 0
    for pair in pairs:
        for tf in tfs:
            try:
                save(pair, tf)
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"  FAILED {pair} {tf}: {e}")
    print("Done." + (f" {failures} failure(s)." if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

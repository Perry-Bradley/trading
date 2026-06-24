"""Download historical forex OHLCV data via yfinance.

Usage:
    python -m src.data.fetch --pair EURUSD --timeframe D1
    python -m src.data.fetch --all          # every pair, every timeframe

Data is saved as parquet under data/<PAIR>_<TIMEFRAME>.parquet with a tz-naive
DatetimeIndex and columns: open, high, low, close, volume.
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


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise a yfinance frame to lowercase OHLCV with a clean index."""
    # yfinance returns a MultiIndex column frame when given a single ticker too.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep].copy()
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index.name = "time"
    return df.dropna(subset=["open", "high", "low", "close"])


def _sanitize(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce OHLC integrity: high must contain open/close, low likewise.

    Yahoo's forex feed occasionally returns a high/low that doesn't bracket the
    open/close (mostly sub-pip rounding, but rarely a badly wrong bar). We clamp
    rather than drop so the time series stays continuous. Returns a copy.
    """
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
    """Which live source handles this pair (for display / docs)."""
    if pair in config.CRYPTO:
        return "binance"
    elif pair == "V100" or pair == "V25":
        return "deriv"
    else:
        return "twelvedata"


def fetch(pair: str, timeframe: str) -> pd.DataFrame:
    """Route to the best available source.

    crypto  -> Binance (real-time, no key)
    v100/v25 -> Deriv API
    forex/idx -> Twelve Data
    """
    if pair not in config.PAIRS:
        raise ValueError(f"Unknown pair {pair!r}. Known: {list(config.PAIRS)}")
    if timeframe not in config.TIMEFRAMES:
        raise ValueError(f"Unknown timeframe {timeframe!r}. Known: {list(config.TIMEFRAMES)}")

    if pair in config.CRYPTO:
        from src.data.sources import binance
        return _sanitize(binance.fetch_ohlcv(pair, timeframe))
    elif pair == "V100" or pair == "V25":
        from src.data.sources import deriv_data
        return _sanitize(deriv_data.fetch_ohlcv(pair, timeframe))
    else:
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
    p = argparse.ArgumentParser(description="Fetch forex OHLCV data.")
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
            except Exception as e:  # noqa: BLE001 - report and continue
                failures += 1
                print(f"  FAILED {pair} {tf}: {e}")
    print("Done." + (f" {failures} failure(s)." if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

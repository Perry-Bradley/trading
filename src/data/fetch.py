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
import yfinance as yf

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


def _resample_h4(h1: pd.DataFrame) -> pd.DataFrame:
    """Build H4 candles from H1 data."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    cols = [c for c in agg if c in h1.columns]
    return h1.resample("4h").agg({c: agg[c] for c in cols}).dropna(subset=["open"])


def fetch(pair: str, timeframe: str) -> pd.DataFrame:
    if pair not in config.YF_TICKERS:
        raise ValueError(f"Unknown pair {pair!r}. Known: {list(config.YF_TICKERS)}")
    if timeframe not in config.TIMEFRAMES:
        raise ValueError(f"Unknown timeframe {timeframe!r}. Known: {list(config.TIMEFRAMES)}")

    ticker = config.YF_TICKERS[pair]
    spec = config.TIMEFRAMES[timeframe]

    df = yf.download(
        ticker,
        interval=spec["yf_interval"],
        period=spec["yf_period"],
        auto_adjust=False,
        progress=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"No data returned for {pair} {timeframe} ({ticker})")

    df = _flatten(df)
    if timeframe == "H4":
        df = _resample_h4(df)
    df = _sanitize(df)
    return df


def save(pair: str, timeframe: str) -> pd.DataFrame:
    df = fetch(pair, timeframe)
    out = config.DATA_DIR / f"{pair}_{timeframe}.parquet"
    df.to_parquet(out)
    span = f"{df.index.min()} -> {df.index.max()}"
    print(f"  saved {pair} {timeframe:>3}: {len(df):>6} bars  ({span})  -> {out.name}")
    return df


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch forex OHLCV data.")
    p.add_argument("--pair", choices=list(config.YF_TICKERS), help="Single pair to fetch.")
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

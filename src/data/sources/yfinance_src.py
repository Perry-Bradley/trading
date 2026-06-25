"""Yahoo Finance fallback for forex/gold — free, no API key (~15 min delay)."""
from __future__ import annotations

import pandas as pd
import yfinance as yf

import config

# Yahoo tickers for our instruments
_TICKER = {
    "XAUUSD": "GC=F",
    "BTCUSD": "BTC-USD",
}


def _ticker(pair: str) -> str:
    return _TICKER.get(pair, f"{pair}=X")


def fetch_ohlcv(pair: str, tf: str) -> pd.DataFrame:
    spec = config.TIMEFRAMES[tf]
    raw = yf.download(
        _ticker(pair),
        period=spec["yf_period"],
        interval=spec["yf_interval"],
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance: no data for {pair} {tf}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw.rename(columns=str.lower)
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep].copy()
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index.name = "time"
    df = df.dropna(subset=["open", "high", "low", "close"])

    # H4 is resampled from H1 bars in our ladder
    if tf == "H4":
        df = (
            df.resample("4h", label="left", closed="left")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna(subset=["open", "high", "low", "close"])
        )
    return df

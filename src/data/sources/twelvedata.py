"""Twelve Data market-data source (forex) — real-time-ish with a free API key.

Set TWELVEDATA_KEY to enable. Free tier is rate-limited (~8 req/min, 800/day),
which is fine for our low-frequency scanning. If the key is missing or a request
fails (e.g. rate limit), the caller falls back to yfinance.
"""
from __future__ import annotations

import os

import pandas as pd
import requests

INTERVAL = {"D1": "1day", "H4": "4h", "H1": "1h", "M30": "30min"}


def available() -> bool:
    return bool(os.environ.get("TWELVEDATA_KEY"))


def _symbol(pair: str) -> str:
    return f"{pair[:3]}/{pair[3:]}"


def fetch_ohlcv(pair: str, tf: str, outputsize: int = 5000) -> pd.DataFrame:
    key = os.environ.get("TWELVEDATA_KEY")
    if not key:
        raise RuntimeError("TWELVEDATA_KEY not set")
    url = ("https://api.twelvedata.com/time_series"
           f"?symbol={_symbol(pair)}&interval={INTERVAL[tf]}"
           f"&outputsize={outputsize}&apikey={key}&format=JSON")
    j = requests.get(url, timeout=30).json()
    if "values" not in j:
        raise RuntimeError(f"twelvedata: {j.get('message', j)}")
    df = pd.DataFrame(j["values"])
    df["time"] = pd.to_datetime(df["datetime"])
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
    else:
        df["volume"] = 0.0          # forex has no volume from Twelve Data
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]].sort_index()
    df.index.name = "time"
    return df

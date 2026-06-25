"""Twelve Data market-data source (forex + gold) — live with API key.

Set TWELVEDATA_KEY on Railway (or TWELVE_DATA_API_KEY). Free tier: ~8 req/min.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

INTERVAL = {"D1": "1day", "H4": "4h", "H1": "1h", "M30": "30min"}

# Free tier allows ~8 requests/min; keep >=8s between calls.
_MIN_SPACING = 8.0
_last_call = [0.0]

_KEY_NAMES = ("TWELVEDATA_KEY", "TWELVE_DATA_API_KEY", "TWELVE_DATA_KEY", "TWELVEDATA_API_KEY")


def api_key() -> str:
    for name in _KEY_NAMES:
        v = (os.environ.get(name) or "").strip()
        if v:
            return v
    return ""


def _throttle() -> None:
    wait = _MIN_SPACING - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()


def available() -> bool:
    return bool(api_key())


def _symbol(pair: str) -> str:
    if pair == "XAUUSD":
        return "XAU/USD"
    return f"{pair[:3]}/{pair[3:]}"


def fetch_ohlcv(pair: str, tf: str, outputsize: int = 5000) -> pd.DataFrame:
    key = api_key()
    if not key:
        raise RuntimeError(
            "TWELVEDATA_KEY not set — add it to Railway variables for live forex data"
        )
    url = ("https://api.twelvedata.com/time_series"
           f"?symbol={_symbol(pair)}&interval={INTERVAL[tf]}"
           f"&outputsize={outputsize}&apikey={key}&format=JSON")
    _throttle()
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
        df["volume"] = 0.0
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]].sort_index()
    df.index.name = "time"
    return df

"""Finnhub REST API — historical forex/gold OHLCV for analysis and backtests.

Set FINNHUB_KEY (or FINNHUB_API_KEY) on Railway. Free tier: 60 REST calls/min.
WebSocket live ticks are handled by finnhub_ws.py.
"""
from __future__ import annotations

import os
import time

import pandas as pd
import requests

BASE = "https://finnhub.io/api/v1"

_KEY_NAMES = ("FINNHUB_KEY", "FINNHUB_API_KEY", "FINNHUB_TOKEN")

# Finnhub OANDA forex symbols
PAIR_SYMBOL = {
    "EURUSD": "OANDA:EUR_USD",
    "GBPUSD": "OANDA:GBP_USD",
    "AUDUSD": "OANDA:AUD_USD",
    "XAUUSD": "OANDA:XAU_USD",
}

RESOLUTION = {"M30": "30", "H1": "60", "D1": "D"}
BAR_SECONDS = {"M30": 30 * 60, "H1": 3600, "D1": 86400, "H4": 4 * 3600}


def api_key() -> str:
    for name in _KEY_NAMES:
        v = (os.environ.get(name) or "").strip()
        if v:
            return v
    return ""


def available() -> bool:
    return bool(api_key())


def symbol_for(pair: str) -> str:
    sym = PAIR_SYMBOL.get(pair)
    if not sym:
        raise ValueError(f"No Finnhub symbol for {pair!r}")
    return sym


def pair_from_symbol(symbol: str) -> str | None:
    for pair, sym in PAIR_SYMBOL.items():
        if sym == symbol:
            return pair
    return None


def _to_h4(df_h1: pd.DataFrame) -> pd.DataFrame:
    if df_h1.empty:
        return df_h1
    out = df_h1.resample("4h", label="left", closed="left").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna()
    out.index.name = "time"
    return out


def _fetch_candles(symbol: str, resolution: str, frm: int, to: int) -> pd.DataFrame:
    key = api_key()
    if not key:
        raise RuntimeError("FINNHUB_KEY not set — add it to Railway for forex data")
    r = requests.get(
        f"{BASE}/forex/candle",
        params={"symbol": symbol, "resolution": resolution, "from": frm, "to": to, "token": key},
        timeout=45,
    )
    r.raise_for_status()
    j = r.json()
    if j.get("s") != "ok":
        raise RuntimeError(f"finnhub: {j.get('s')} {j}")
    if not j.get("t"):
        raise RuntimeError(f"finnhub: no candles for {symbol} {resolution}")
    df = pd.DataFrame({
        "open": j["o"], "high": j["h"], "low": j["l"], "close": j["c"],
        "volume": j.get("v", [0.0] * len(j["t"])),
    })
    df.index = pd.to_datetime(j["t"], unit="s")
    df.index.name = "time"
    return df.sort_index()


def fetch_ohlcv(pair: str, tf: str, bars: int = 5000) -> pd.DataFrame:
    if tf == "H4":
        return _to_h4(fetch_ohlcv(pair, "H1", bars=bars * 4))
    if tf not in RESOLUTION:
        raise ValueError(f"Finnhub REST does not support timeframe {tf!r}")
    symbol = symbol_for(pair)
    res = RESOLUTION[tf]
    now = int(time.time())
    sec = BAR_SECONDS[tf]
    frm = now - sec * bars
    return _fetch_candles(symbol, res, frm, now)

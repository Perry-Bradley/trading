"""Deriv WebSocket API data source for proprietary indices (V100, V25).

Connects to Deriv servers to fetch real-time and historical OHLCV data.
Does NOT require an MT5 terminal. An API token is optional for public 
ticks, but required for trading (which this module doesn't do yet).
Works perfectly on Linux/Railway.
"""
from __future__ import annotations

import json
import pandas as pd
from websockets.sync.client import connect

# map our pairs to Deriv symbols
DERIV_SYMBOLS = {
    "V100": "R_100",
    "V25": "R_25",
}

# map our timeframes to Deriv granularity in seconds
GRANULARITY = {
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
}

def fetch_ohlcv(pair: str, tf: str) -> pd.DataFrame:
    symbol = DERIV_SYMBOLS.get(pair)
    if not symbol:
        raise ValueError(f"Unknown Deriv pair: {pair}")
    
    granularity = GRANULARITY.get(tf)
    if not granularity:
        raise ValueError(f"Unknown timeframe for Deriv: {tf}")

    req = {
        "ticks_history": symbol,
        "adjust_start_time": 1,
        "count": 5000,
        "end": "latest",
        "style": "candles",
        "granularity": granularity
    }

    # app_id 1089 is the default public testing app ID
    with connect("wss://ws.binaryws.com/websockets/v3?app_id=1089") as websocket:
        websocket.send(json.dumps(req))
        resp = json.loads(websocket.recv())

    if "error" in resp:
        raise RuntimeError(f"Deriv API error: {resp['error'].get('message', resp['error'])}")

    candles = resp.get("candles", [])
    if not candles:
        raise RuntimeError(f"No candles returned for {pair} on Deriv")

    df = pd.DataFrame(candles)
    # The API returns epoch, open, high, low, close
    df["time"] = pd.to_datetime(df["epoch"], unit="s")
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    
    df["volume"] = 0.0  # Deriv volatility indices do not have real volume
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]]
    
    return df

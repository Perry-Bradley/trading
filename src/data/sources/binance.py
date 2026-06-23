"""Binance market-data source (crypto) — free, real-time, no API key for data.

Public klines REST, paged backwards to build a decent history. Native intervals
(incl. 4h) so no resampling needed. Works globally (incl. Cameroon) and on Railway.
"""
from __future__ import annotations

import pandas as pd
import requests

INTERVAL = {"D1": "1d", "H4": "4h", "H1": "1h", "M30": "30m"}
# our pair name -> Binance symbol (Binance quotes crypto in USDT)
SYMBOL = {"BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT", "SOLUSD": "SOLUSDT"}
# data-api.binance.vision is the public data-only mirror (no auth, not geo-blocked
# like api.binance.com which returns 451 in many regions). Try mirrors in order.
HOSTS = ["https://data-api.binance.vision", "https://api.binance.us", "https://api.binance.com"]


def _symbol(pair: str) -> str:
    return SYMBOL.get(pair, pair.replace("USD", "USDT"))


def _klines(sym: str, interval: str, end) -> list:
    last_err = None
    for host in HOSTS:
        url = f"{host}/api/v3/klines?symbol={sym}&interval={interval}&limit=1000"
        if end:
            url += f"&endTime={end}"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return data
            last_err = f"{host} -> {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{host} -> {e}"
    raise RuntimeError(f"all Binance hosts failed ({last_err})")


def fetch_ohlcv(pair: str, tf: str, bars: int = 1500) -> pd.DataFrame:
    sym, interval = _symbol(pair), INTERVAL[tf]
    rows: list = []
    end = None
    while len(rows) < bars:
        data = _klines(sym, interval, end)
        if not data:
            break
        rows = data + rows
        end = data[0][0] - 1          # page backwards from the oldest bar
        if len(data) < 1000:
            break
    rows = rows[-bars:]
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume",
                                     "ct", "q", "n", "tb", "tq", "ig"])
    df["time"] = pd.to_datetime(df["t"], unit="ms")
    df = df.set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)
    df.index.name = "time"
    return df[~df.index.duplicated(keep="last")].sort_index()

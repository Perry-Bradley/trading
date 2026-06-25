"""Finnhub WebSocket — live forex trade stream for real-time prices and forming candles.

Subscribes to OANDA forex symbols, aggregates ticks into M30/H1 bars, and merges
them into parquet so signals and the dashboard see the live forming candle.
"""
from __future__ import annotations

import json
import threading
import time

import pandas as pd
from websockets.sync.client import connect

import config
from src.data.sources import finnhub

WS_URL = "wss://ws.finnhub.io"

_lock = threading.Lock()
_quotes: dict[str, float] = {}
_forming: dict[tuple[str, str], dict] = {}
_status = {
    "running": False,
    "connected": False,
    "last_trade": None,
    "last_error": None,
    "trades": 0,
}
_started = False
_flush_interval = 10.0


def _bar_floor(ts_ms: int, minutes: int) -> pd.Timestamp:
    ts = pd.Timestamp(ts_ms, unit="ms", tz="UTC").tz_localize(None)
    if minutes == 30:
        return ts.floor("30min")
    if minutes == 60:
        return ts.floor("1h")
    return ts.floor(f"{minutes}min")


def _on_trade(symbol: str, price: float, ts_ms: int) -> None:
    pair = finnhub.pair_from_symbol(symbol)
    if not pair:
        return
    with _lock:
        _quotes[pair] = price
        _status["trades"] += 1
        _status["last_trade"] = pd.Timestamp(ts_ms, unit="ms").strftime("%Y-%m-%d %H:%M:%S UTC")
        for tf, mins in (("M30", 30), ("H1", 60)):
            start = _bar_floor(ts_ms, mins)
            key = (pair, tf)
            fb = _forming.get(key)
            if fb is None or fb["start"] != start:
                _forming[key] = {
                    "start": start, "open": price, "high": price,
                    "low": price, "close": price, "volume": 0.0,
                }
            else:
                fb["high"] = max(fb["high"], price)
                fb["low"] = min(fb["low"], price)
                fb["close"] = price


def _merge_bar(pair: str, tf: str, bar: dict) -> None:
    from src.data import io
    path = config.DATA_DIR / f"{pair}_{tf}.parquet"
    ts = bar["start"]
    row = {
        "open": float(bar["open"]), "high": float(bar["high"]),
        "low": float(bar["low"]), "close": float(bar["close"]),
        "volume": float(bar.get("volume", 0)),
    }

    def _update(df):
        if df is None or len(df) == 0:
            return pd.DataFrame([row], index=pd.DatetimeIndex([ts], name="time"))
        if ts in df.index:
            df.loc[ts, "high"] = max(float(df.loc[ts, "high"]), row["high"])
            df.loc[ts, "low"] = min(float(df.loc[ts, "low"]), row["low"])
            df.loc[ts, "close"] = row["close"]
        elif df.index[-1] < ts:
            df.loc[ts] = row
            df = df.sort_index()
        else:
            return None  # stale tick older than history — ignore
        if len(df) > 5000:
            df = df.iloc[-5000:]
        return df

    # Atomic, lock-serialized read-modify-write (won't collide with REST writes).
    io.atomic_update(path, _update)


def _rebuild_h4(pair: str) -> None:
    from src.data import io
    h1 = io.safe_read_parquet(config.DATA_DIR / f"{pair}_H1.parquet")
    if h1 is None or h1.empty:
        return
    h4 = finnhub._to_h4(h1)
    if not h4.empty:
        io.atomic_to_parquet(h4, config.DATA_DIR / f"{pair}_H4.parquet")


def flush_to_disk() -> None:
    """Merge in-memory forming bars into parquet (call periodically)."""
    with _lock:
        snap = dict(_forming)
    for (pair, tf), bar in snap.items():
        try:
            _merge_bar(pair, tf, bar)
            if tf == "H1":
                _rebuild_h4(pair)
        except Exception as e:  # noqa: BLE001
            _status["last_error"] = str(e)[:120]


def live_quote(pair: str) -> float | None:
    with _lock:
        return _quotes.get(pair)


def status() -> dict:
    with _lock:
        return {
            "running": _status["running"],
            "connected": _status["connected"],
            "trades": _status["trades"],
            "last_trade": _status["last_trade"],
            "last_error": _status["last_error"],
            "quotes": {p: _quotes[p] for p in sorted(_quotes)},
        }


def _flush_loop() -> None:
    while _status["running"]:
        flush_to_disk()
        time.sleep(_flush_interval)


def _ws_loop() -> None:
    key = finnhub.api_key()
    if not key:
        _status["last_error"] = "FINNHUB_KEY not set"
        return
    symbols = [finnhub.symbol_for(p) for p in config.PAIRS if p in finnhub.PAIR_SYMBOL]
    url = f"{WS_URL}?token={key}"
    backoff = 5  # seconds, grows on repeated failures (Finnhub free tier = 1 connection/key)
    while _status["running"]:
        try:
            with connect(url, open_timeout=20) as ws:
                for sym in symbols:
                    ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
                _status["connected"] = True
                _status["last_error"] = None
                backoff = 5  # reset after a clean connect
                print(f"[finnhub-ws] connected — {len(symbols)} forex symbols")
                while _status["running"]:
                    raw = ws.recv()
                    msg = json.loads(raw)
                    if msg.get("type") == "trade":
                        for t in msg.get("data", []):
                            _on_trade(t["s"], float(t["p"]), int(t["t"]))
                    elif msg.get("type") == "error":
                        _status["last_error"] = str(msg.get("msg", msg))[:120]
        except Exception as e:  # noqa: BLE001
            _status["connected"] = False
            _status["last_error"] = str(e)[:120]
            # 429 = another connection holds the key (e.g. old container during a
            # redeploy). Back off harder so we don't fight it; otherwise grow gently.
            is_429 = "429" in str(e)
            wait = 60 if is_429 else backoff
            print(f"[finnhub-ws] disconnected ({str(e)[:80]}) — retry in {wait}s")
            time.sleep(wait)
            if not is_429:
                backoff = min(backoff * 2, 60)


def start_background() -> None:
    global _started
    if _started or not finnhub.available():
        return
    _started = True
    _status["running"] = True
    threading.Thread(target=_ws_loop, daemon=True, name="finnhub-ws").start()
    threading.Thread(target=_flush_loop, daemon=True, name="finnhub-flush").start()
    print("[finnhub-ws] background stream starting")

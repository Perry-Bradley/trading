"""Twelve Data market-data source (forex + gold) — historical OHLC for analysis.

Used for HISTORICAL candles only. Live ticks come from Finnhub WebSocket
(finnhub_ws.py); Finnhub's free tier blocks REST candles (HTTP 403), so we use
Twelve Data for the history the SMC/MSNR analysis runs on.

Configure one or more keys (free tier: 800 credits/day, 8 req/min each):
  TWELVEDATA_KEY=primary
  TWELVEDATA_KEYS=key2,key3,key4,key5      (comma- or semicolon-separated)
  TWELVEDATA_KEY_2=...  TWELVEDATA_KEY_3=...  etc.

When a key hits its daily credits or per-minute rate limit, the pool tests the
next key and rotates automatically — add as many keys as you like.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import threading
import time

import pandas as pd
import requests

INTERVAL = {"D1": "1day", "H4": "4h", "H1": "1h", "M30": "30min"}

# Free tier is 8 req/min per key; space calls ~8.5s apart to stay safe.
_MIN_SPACING = 8.5
_last_call = [0.0]
_throttle_lock = threading.Lock()

_KEY_NAMES = ("TWELVEDATA_KEY", "TWELVE_DATA_API_KEY", "TWELVE_DATA_KEY", "TWELVEDATA_API_KEY")

_EXHAUSTED_PATTERNS = (
    r"run out of api credits",
    r"api credit limit",
    r"limit for the day",
    r"daily limit",
    r"maximum usage",
)
_RATE_LIMIT_PATTERNS = (
    r"run out of api credits for the current minute",
    r"current limit being",
    r"rate limit",
    r"too many requests",
)


class KeyExhausted(Exception):
    """Key cannot be used right now (credits or rate limit)."""


class KeyPool:
    """Round-robin pool with automatic failover on credit / rate-limit errors."""

    def __init__(self) -> None:
        self._keys = self._load_keys()
        self._idx = 0
        self._lock = threading.Lock()
        # key -> unix timestamp when key becomes usable again
        self._cooldown: dict[str, float] = {}
        self._stats: dict[str, dict] = {k: {"ok": 0, "fail": 0, "last_error": ""} for k in self._keys}

    @staticmethod
    def _load_keys() -> list[str]:
        keys: list[str] = []
        for name in _KEY_NAMES:
            v = (os.environ.get(name) or "").strip()
            if v and v not in keys:
                keys.append(v)
        bulk = (os.environ.get("TWELVEDATA_KEYS") or "").replace(";", ",")
        for part in bulk.split(","):
            k = part.strip()
            if k and k not in keys:
                keys.append(k)
        for i in range(2, 32):
            v = (os.environ.get(f"TWELVEDATA_KEY_{i}") or "").strip()
            if v and v not in keys:
                keys.append(v)
        return keys

    def reload(self) -> None:
        """Re-read keys from the environment (e.g. after adding more at runtime)."""
        with self._lock:
            for k in self._load_keys():
                if k not in self._keys:
                    self._keys.append(k)
                    self._stats[k] = {"ok": 0, "fail": 0, "last_error": ""}

    def _usable(self, key: str) -> bool:
        until = self._cooldown.get(key, 0)
        return time.time() >= until

    def _mask(self, key: str) -> str:
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}…{key[-4:]}"

    def next_key(self) -> str | None:
        with self._lock:
            if not self._keys:
                return None
            n = len(self._keys)
            for _ in range(n):
                key = self._keys[self._idx % n]
                self._idx += 1
                if self._usable(key):
                    return key
            return None

    def mark_ok(self, key: str) -> None:
        with self._lock:
            self._stats.setdefault(key, {"ok": 0, "fail": 0, "last_error": ""})
            self._stats[key]["ok"] += 1

    def mark_failed(self, key: str, msg: str) -> None:
        low = msg.lower()
        daily = any(re.search(p, low) for p in _EXHAUSTED_PATTERNS)
        rate = any(re.search(p, low) for p in _RATE_LIMIT_PATTERNS)
        with self._lock:
            self._stats.setdefault(key, {"ok": 0, "fail": 0, "last_error": ""})
            self._stats[key]["fail"] += 1
            self._stats[key]["last_error"] = msg[:120]
            if daily and not rate:
                # Daily quota — rest until next UTC midnight
                now = _dt.datetime.utcnow()
                nxt = (now + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                self._cooldown[key] = nxt.timestamp()
                print(f"[twelvedata] key {self._mask(key)} daily limit — cooldown until UTC midnight")
            else:
                # Per-minute rate limit — short backoff
                self._cooldown[key] = time.time() + 65
                print(f"[twelvedata] key {self._mask(key)} rate-limited — 65s cooldown, rotating")

    def status(self) -> dict:
        with self._lock:
            active = sum(1 for k in self._keys if self._usable(k))
            rows = []
            for k in self._keys:
                st = self._stats.get(k, {"ok": 0, "fail": 0, "last_error": ""})
                until = self._cooldown.get(k, 0)
                rows.append({
                    "id": self._mask(k),
                    "active": self._usable(k),
                    "ok": st["ok"],
                    "fail": st["fail"],
                    "last_error": st["last_error"] or None,
                    "cooldown_until": _dt.datetime.utcfromtimestamp(until).strftime("%H:%M UTC")
                    if until > time.time() else None,
                })
            return {
                "configured": len(self._keys),
                "active": active,
                "exhausted": len(self._keys) - active,
                "keys": rows,
            }


_pool: KeyPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> KeyPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = KeyPool()
        return _pool


def api_key() -> str:
    return get_pool().next_key() or ""


def available() -> bool:
    return get_pool().status()["configured"] > 0


def pool_status() -> dict:
    return get_pool().status()


def _throttle() -> None:
    with _throttle_lock:
        wait = _MIN_SPACING - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()


def _symbol(pair: str) -> str:
    if pair == "XAUUSD":
        return "XAU/USD"
    return f"{pair[:3]}/{pair[3:]}"


def _fetch_with_key(pair: str, tf: str, key: str, outputsize: int) -> pd.DataFrame:
    url = ("https://api.twelvedata.com/time_series"
           f"?symbol={_symbol(pair)}&interval={INTERVAL[tf]}"
           f"&outputsize={outputsize}&apikey={key}&format=JSON")
    _throttle()
    j = requests.get(url, timeout=30).json()
    if "values" not in j:
        msg = str(j.get("message", j))
        low = msg.lower()
        if any(re.search(p, low) for p in _EXHAUSTED_PATTERNS + _RATE_LIMIT_PATTERNS):
            raise KeyExhausted(msg)
        raise RuntimeError(f"twelvedata: {msg}")
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


def fetch_ohlcv(pair: str, tf: str, outputsize: int = 5000) -> pd.DataFrame:
    if tf not in INTERVAL:
        raise ValueError(f"TwelveData does not support timeframe {tf!r}")
    pool = get_pool()
    pool.reload()  # pick up any keys added since startup
    if not pool._keys:
        raise RuntimeError(
            "No TwelveData keys set — add TWELVEDATA_KEY and optional TWELVEDATA_KEYS"
        )
    last_err: Exception | None = None
    tries = max(len(pool._keys), 1)
    for _ in range(tries):
        key = pool.next_key()
        if not key:
            break
        try:
            df = _fetch_with_key(pair, tf, key, outputsize)
            pool.mark_ok(key)
            return df
        except KeyExhausted as e:
            pool.mark_failed(key, str(e))
            last_err = e
            print(f"  [twelvedata] {pair} {tf}: rotating key ({e})")
            continue
    raise RuntimeError(
        f"All TwelveData keys exhausted or rate-limited{f': {last_err}' if last_err else ''}"
    )

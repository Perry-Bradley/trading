"""Atomic, lock-serialized parquet IO.

Two background threads write the same parquet files — the Finnhub WS flush loop
(forming bars every 10s) and the REST updater/seed (full history). `to_parquet`
is not atomic, so concurrent writers produced truncated / 0-byte files and
"Invalid column metadata" read errors. Everything goes through here instead:

  - writes go to a temp file then os.replace() (atomic rename on the same fs),
    so a reader never sees a half-written file;
  - a per-path lock serializes writers to the same file;
  - reads detect a 0-byte / corrupt file, delete it, and return None so the
    caller refetches instead of crashing.
"""
from __future__ import annotations

import os
import threading
from typing import Callable

import pandas as pd

_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    with _guard:
        lk = _locks.get(path)
        if lk is None:
            lk = threading.Lock()
            _locks[path] = lk
        return lk


def _write(df: pd.DataFrame, path: str) -> None:
    tmp = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}"
    df.to_parquet(tmp)
    os.replace(tmp, path)  # atomic on the same filesystem


def safe_read_parquet(path, **kw):
    """Read parquet; on a missing/0-byte/corrupt file, remove it and return None."""
    p = str(path)
    try:
        if not os.path.exists(p):
            return None
        if os.path.getsize(p) == 0:
            os.remove(p)
            return None
        return pd.read_parquet(p, **kw)
    except Exception:  # noqa: BLE001 — corrupt file: drop it so it gets refetched
        try:
            os.remove(p)
        except OSError:
            pass
        return None


def atomic_to_parquet(df: pd.DataFrame, path) -> None:
    """Replace a parquet file atomically, serialized per path."""
    p = str(path)
    with _lock_for(p):
        _write(df, p)


def atomic_update(path, fn: Callable) -> None:
    """Read-modify-write a parquet file while holding its lock the whole time.

    `fn` receives the current DataFrame (or None if missing/corrupt) and returns
    the new DataFrame to persist (or None to leave the file untouched).
    """
    p = str(path)
    with _lock_for(p):
        cur = None
        if os.path.exists(p) and os.path.getsize(p) > 0:
            try:
                cur = pd.read_parquet(p)
            except Exception:  # noqa: BLE001
                cur = None
        out = fn(cur)
        if out is not None:
            _write(out, p)

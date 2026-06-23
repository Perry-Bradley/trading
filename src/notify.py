"""Alerts / notifications across channels.

Always: console + a persistent `alerts.log`.
Optional (zero extra deps, enabled by env vars):
  * Telegram push  -> set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID

Notification failures never raise — a broken alert channel must not crash trading.
"""
from __future__ import annotations

import datetime as _dt
import os

import requests

import config

ALERTS_LOG = config.ROOT / "alerts.log"


def _telegram(text: str) -> None:
    tok = os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=10)
    except Exception:  # noqa: BLE001 - never let alerts break the loop
        pass


def notify(title: str, body: str = "") -> None:
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"{title}" + (f"\n{body}" if body else "")
    print(f"[ALERT {ts}] {title}" + (f" — {body}" if body else ""))
    try:
        with open(ALERTS_LOG, "a", encoding="utf-8") as f:
            f.write(f"{ts} | {title} | {body}\n")
    except Exception:  # noqa: BLE001
        pass
    _telegram(f"{ts}\n{text}")

"""Detailed trade journal — a full, append-only record of everything the engine does.

Every entry and every close is written as a row to `data/journal.csv` (human- and
spreadsheet-readable), and `track_record()` summarises the resolved trades so you
can see exactly how it's playing out: win rate, expectancy, total R, P&L.

Broker-agnostic: the journal is the single source of truth for the track record,
so it works the same whether you run paper, MT5 or OANDA.
"""
from __future__ import annotations

import csv

import config

JOURNAL = config.DATA_DIR / "journal.csv"
FIELDS = ["ts", "event", "pair", "direction", "tf", "entry", "stop", "target",
          "conf", "size", "outcome", "r", "pnl", "nav"]


def record(row: dict) -> None:
    new = not JOURNAL.exists()
    with open(JOURNAL, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def _rows() -> list[dict]:
    if not JOURNAL.exists():
        return []
    with open(JOURNAL, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def recent(n: int = 100) -> list[dict]:
    """Most recent journal rows (newest first) — for the dashboard feed."""
    return _rows()[-n:][::-1]


def count(event: str | None = None) -> int:
    rows = _rows()
    if event is None:
        return len(rows)
    return sum(1 for r in rows if r.get("event") == event)


def last_ts() -> str | None:
    rows = _rows()
    return rows[-1]["ts"] if rows else None


def track_record(last_n: int | None = None) -> dict:
    """Summarise resolved (closed) trades from the journal."""
    closes = [r for r in _rows() if r["event"] == "CLOSE"]
    if last_n:
        closes = closes[-last_n:]
    n = len(closes)
    if n == 0:
        return {"resolved": 0, "wins": 0, "win_rate": 0.0, "expectancy_r": 0.0,
                "total_r": 0.0, "total_pnl": 0.0, "profit_factor": 0.0}
    rs = [float(r["r"] or 0) for r in closes]
    pnls = [float(r["pnl"] or 0) for r in closes]
    wins = sum(1 for r in closes if r["outcome"] == "win")
    gross_w = sum(x for x in rs if x > 0)
    gross_l = -sum(x for x in rs if x < 0)
    return {
        "resolved": n,
        "wins": wins,
        "win_rate": wins / n,
        "expectancy_r": sum(rs) / n,
        "total_r": sum(rs),
        "total_pnl": sum(pnls),
        "profit_factor": (gross_w / gross_l) if gross_l > 0 else float("inf"),
    }


def summary_line() -> str:
    t = track_record()
    if t["resolved"] == 0:
        return "no resolved trades yet"
    pf = "inf" if t["profit_factor"] == float("inf") else f"{t['profit_factor']:.2f}"
    return (f"{t['wins']}/{t['resolved']} wins ({t['win_rate']*100:.0f}%), "
            f"exp {t['expectancy_r']:+.2f}R, total {t['total_r']:+.1f}R, PF {pf}")

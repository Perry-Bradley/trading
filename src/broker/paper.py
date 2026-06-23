"""Local paper-trading broker.

Tracks a virtual account in a JSON file. Opens positions from signals (sizing in
account currency by risk), and on sync() resolves each open trade against real
price data — walking only the bars AFTER the entry, stop-first on ambiguity, with
the same per-pair transaction cost the backtester uses. P&L is booked in R.

No credentials, no network — works immediately and is the tested path.
"""
from __future__ import annotations

import json

import pandas as pd

import config
from src.broker.base import Broker, Position
from src.data import fetch

COST_PIPS = {"EURUSD": 1.2, "GBPUSD": 1.5, "AUDUSD": 1.5,
             "EURNZD": 3.0, "CHFJPY": 2.0, "BTCUSD": 25.0}


class PaperBroker(Broker):
    name = "paper"

    def __init__(self, state_path=None, start_balance: float = 10_000.0,
                 base_risk_pct: float = 0.01):
        self.path = state_path or (config.DATA_DIR / "paper_state.json")
        self.base_risk_pct = base_risk_pct
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
        else:
            self.state = {"balance": start_balance, "start_balance": start_balance,
                          "open": [], "closed": []}
            self._save()

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.state, indent=2, default=str))

    def nav(self) -> float:
        return float(self.state["balance"])

    def open_positions(self) -> list[Position]:
        return [Position.from_dict(d) for d in self.state["open"]]

    def open_trade(self, sig: dict, size: float) -> Position | None:
        # Note: no one-per-pair block — paper TESTS every distinct signal so the
        # accuracy/track-record reflects all the model's predictions (the id check
        # below still prevents re-opening the same signal twice).
        if size <= 0:
            return None
        risk_dist = abs(sig["entry"] - sig["stop"])
        if risk_dist <= 0:
            return None
        risk_amount = self.nav() * self.base_risk_pct * size
        units = risk_amount / risk_dist
        pos = Position(
            id=f"{sig['pair']}-{pd.Timestamp(sig['time']).isoformat()}",
            pair=sig["pair"], tf=sig["tf"], direction=sig["direction"],
            entry=sig["entry"], stop=sig["stop"], target=sig["target"],
            size=size, units=units if sig["direction"] == "long" else -units,
            risk_amount=risk_amount, open_time=pd.Timestamp(sig["time"]).isoformat(),
            features=sig.get("features", {}),
        )
        # don't re-open an id we've already traded
        if any(p["id"] == pos.id for p in self.state["open"] + self.state["closed"]):
            return None
        self.state["open"].append(pos.to_dict())
        self._save()
        return pos

    def sync(self) -> list[Position]:
        closed = []
        still_open = []
        for d in self.state["open"]:
            pos = Position.from_dict(d)
            res = self._resolve(pos)
            if res is None:
                still_open.append(d)
            else:
                closed.append(res)
                self.state["closed"].append(res.to_dict())
                self.state["balance"] = float(self.state["balance"]) + res.pnl
        self.state["open"] = still_open
        self._save()
        return closed

    def _resolve(self, pos: Position) -> Position | None:
        """Return the closed position if SL/TP hit after entry, else None."""
        try:
            df = fetch.load(pos.pair, pos.tf)
        except FileNotFoundError:
            return None
        after = df[df.index > pd.Timestamp(pos.open_time)]
        if after.empty:
            return None
        risk_dist = abs(pos.entry - pos.stop)
        target_r = abs(pos.target - pos.entry) / risk_dist
        cost_r = (COST_PIPS.get(pos.pair, 1.5) * config.pip_size(pos.pair)) / risk_dist
        long = pos.direction == "long"
        for t, row in after.iterrows():
            hi, lo = row["high"], row["low"]
            hit = None
            if long:
                if lo <= pos.stop:
                    hit = ("loss", pos.stop, -1.0)
                elif hi >= pos.target:
                    hit = ("win", pos.target, target_r)
            else:
                if hi >= pos.stop:
                    hit = ("loss", pos.stop, -1.0)
                elif lo <= pos.target:
                    hit = ("win", pos.target, target_r)
            if hit:
                outcome, exitp, r = hit
                r -= cost_r
                pos.status = "closed"
                pos.exit, pos.exit_time, pos.outcome = float(exitp), t.isoformat(), outcome
                pos.r = float(r)
                pos.pnl = float(pos.risk_amount * r)
                return pos
        return None

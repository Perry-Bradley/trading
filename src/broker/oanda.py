"""OANDA v20 broker (practice/live).

Requires environment variables:
    OANDA_TOKEN     your v20 API token
    OANDA_ACCOUNT   your account id (e.g. 101-001-1234567-001)
    OANDA_ENV       "practice" (default) or "live"

Places market orders with attached stop-loss / take-profit, reports NAV, and on
sync() detects trades that closed broker-side and books their realised P&L (so the
online model can learn from them too).

NOTE: written to the documented v20 REST spec but UNTESTED without live
credentials. Validate on a practice account before trusting it. Network/HTTP
errors are swallowed so a broker hiccup never crashes the trading loop.
"""
from __future__ import annotations

import json
import os

import pandas as pd
import requests

import config
from src.broker.base import Broker, Position

HOSTS = {"practice": "https://api-fxpractice.oanda.com",
         "live": "https://api-fxtrade.oanda.com"}


def _instrument(pair: str) -> str:
    return f"{pair[:3]}_{pair[3:]}"


def _price_fmt(pair: str, price: float) -> str:
    dp = 3 if pair.endswith("JPY") else (1 if pair == "BTCUSD" else 5)
    return f"{price:.{dp}f}"


class OandaBroker(Broker):
    name = "oanda"

    def __init__(self, base_risk_pct: float = 0.01, state_path=None):
        self.token = os.environ.get("OANDA_TOKEN")
        self.account = os.environ.get("OANDA_ACCOUNT")
        self.host = HOSTS.get(os.environ.get("OANDA_ENV", "practice"), HOSTS["practice"])
        self.base_risk_pct = base_risk_pct
        self.path = state_path or (config.DATA_DIR / "oanda_state.json")
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {"placed": {}}
        if not self.token or not self.account:
            raise RuntimeError("Set OANDA_TOKEN and OANDA_ACCOUNT environment variables.")

    # --- low-level ---
    def _h(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _get(self, path: str):
        try:
            r = requests.get(f"{self.host}{path}", headers=self._h(), timeout=15)
            return r.json() if r.ok else None
        except Exception:  # noqa: BLE001
            return None

    def _save(self):
        self.path.write_text(json.dumps(self.state, indent=2, default=str))

    # --- Broker API ---
    def nav(self) -> float:
        j = self._get(f"/v3/accounts/{self.account}/summary")
        try:
            return float(j["account"]["NAV"])
        except Exception:  # noqa: BLE001
            return 0.0

    def open_positions(self) -> list[Position]:
        j = self._get(f"/v3/accounts/{self.account}/openTrades")
        out = []
        for t in (j or {}).get("trades", []):
            inst = t["instrument"]
            pair = inst.replace("_", "")
            units = float(t["currentUnits"])
            out.append(Position(id=t["id"], pair=pair, tf="?",
                                direction="long" if units > 0 else "short",
                                entry=float(t["price"]), stop=0.0, target=0.0,
                                size=0.0, units=units, risk_amount=0.0,
                                open_time=t.get("openTime", "")))
        return out

    def open_trade(self, sig: dict, size: float) -> Position | None:
        if size <= 0 or self.has_open(sig["pair"]):
            return None
        risk_dist = abs(sig["entry"] - sig["stop"])
        if risk_dist <= 0:
            return None
        units = int(self.nav() * self.base_risk_pct * size / risk_dist)
        if units <= 0:
            return None
        units = units if sig["direction"] == "long" else -units
        body = {"order": {
            "type": "MARKET", "instrument": _instrument(sig["pair"]),
            "units": str(units), "timeInForce": "FOK", "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": _price_fmt(sig["pair"], sig["stop"])},
            "takeProfitOnFill": {"price": _price_fmt(sig["pair"], sig["target"])},
        }}
        try:
            r = requests.post(f"{self.host}/v3/accounts/{self.account}/orders",
                              headers=self._h(), data=json.dumps(body), timeout=15)
            j = r.json()
        except Exception:  # noqa: BLE001
            return None
        tid = (j.get("orderFillTransaction") or {}).get("tradeOpened", {}).get("tradeID")
        if not tid:
            return None
        self.state["placed"][tid] = {"pair": sig["pair"], "tf": sig["tf"],
                                     "features": sig.get("features", {}),
                                     "open_time": str(sig["time"])}
        self._save()
        return Position(id=tid, pair=sig["pair"], tf=sig["tf"], direction=sig["direction"],
                        entry=sig["entry"], stop=sig["stop"], target=sig["target"],
                        size=size, units=units, risk_amount=self.nav() * self.base_risk_pct * size,
                        open_time=str(sig["time"]), features=sig.get("features", {}))

    def sync(self) -> list[Position]:
        """Detect trades that closed broker-side since last sync and book them."""
        open_ids = {p.id for p in self.open_positions()}
        closed = []
        for tid in list(self.state["placed"].keys()):
            if tid in open_ids:
                continue
            j = self._get(f"/v3/accounts/{self.account}/trades/{tid}")
            t = (j or {}).get("trade")
            meta = self.state["placed"].pop(tid)
            if not t or t.get("state") != "CLOSED":
                continue
            pnl = float(t.get("realizedPL", 0.0))
            pos = Position(id=tid, pair=meta["pair"], tf=meta["tf"],
                           direction="long" if float(t.get("initialUnits", 0)) > 0 else "short",
                           entry=float(t.get("price", 0)), stop=0.0, target=0.0, size=0.0,
                           units=float(t.get("initialUnits", 0)), risk_amount=0.0,
                           open_time=meta["open_time"], features=meta["features"],
                           status="closed", exit=float(t.get("averageClosePrice", 0)),
                           exit_time=t.get("closeTime", ""), pnl=pnl,
                           outcome="win" if pnl > 0 else "loss")
            closed.append(pos)
        self._save()
        return closed

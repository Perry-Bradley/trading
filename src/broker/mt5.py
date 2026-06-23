"""MetaTrader 5 broker — the practical execution path outside OANDA's regions.

Works with ANY MT5 broker that accepts your country (Exness, Deriv, XM, FBS,
HFM... all common in Cameroon/Africa). You install the broker's MT5 terminal,
log in once, then this connects to it via the `MetaTrader5` Python package.

Setup:
    pip install MetaTrader5            # Windows only
    # open your broker's MT5 terminal and log in, OR set these env vars:
    #   MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
    # symbols sometimes carry a suffix (e.g. EURUSD.m) -> set MT5_SUFFIX

NOTE: requires Windows + the MT5 terminal; UNTESTED here (no terminal in this
environment). Validate on a DEMO account first. Lot sizing is approximate and
broker-dependent — confirm it matches your intended risk before going live.
"""
from __future__ import annotations

import os

import config
from src.broker.base import Broker, Position


class MT5Broker(Broker):
    name = "mt5"

    def __init__(self, base_risk_pct: float = 0.01):
        try:
            import MetaTrader5 as mt5  # noqa: N813
        except ImportError as e:
            raise RuntimeError("pip install MetaTrader5 (Windows + an MT5 terminal required)") from e
        self.mt5 = mt5
        self.base_risk_pct = base_risk_pct
        self.suffix = os.environ.get("MT5_SUFFIX", "")
        login = os.environ.get("MT5_LOGIN")
        if login:
            ok = mt5.initialize(login=int(login), password=os.environ.get("MT5_PASSWORD"),
                                server=os.environ.get("MT5_SERVER"))
        else:
            ok = mt5.initialize()       # attach to an already-logged-in terminal
        if not ok:
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    def _sym(self, pair: str) -> str:
        return pair + self.suffix

    def nav(self) -> float:
        info = self.mt5.account_info()
        return float(info.equity) if info else 0.0

    def open_positions(self) -> list[Position]:
        out = []
        for p in (self.mt5.positions_get() or []):
            pair = p.symbol.replace(self.suffix, "") if self.suffix else p.symbol
            out.append(Position(id=str(p.ticket), pair=pair, tf="?",
                                direction="long" if p.type == self.mt5.POSITION_TYPE_BUY else "short",
                                entry=float(p.price_open), stop=float(p.sl), target=float(p.tp),
                                size=0.0, units=float(p.volume), risk_amount=0.0,
                                open_time=str(p.time)))
        return out

    def _lots(self, pair: str, risk_amount: float, stop_dist: float) -> float:
        """Approximate lot size so a stop-out costs ~risk_amount. Broker-dependent."""
        si = self.mt5.symbol_info(self._sym(pair))
        if not si or stop_dist <= 0:
            return 0.0
        # value of a 1.0-price move per 1 lot ≈ contract_size (quote-ccy approx)
        loss_per_lot = stop_dist * si.trade_contract_size
        lots = risk_amount / loss_per_lot if loss_per_lot > 0 else 0.0
        step = si.volume_step or 0.01
        lots = max(si.volume_min or 0.01, (int(lots / step) * step))
        return round(lots, 2)

    def open_trade(self, sig: dict, size: float) -> Position | None:
        if size <= 0 or self.has_open(sig["pair"]):
            return None
        sym = self._sym(sig["pair"])
        self.mt5.symbol_select(sym, True)
        risk_dist = abs(sig["entry"] - sig["stop"])
        lots = self._lots(sig["pair"], self.nav() * self.base_risk_pct * size, risk_dist)
        if lots <= 0:
            return None
        is_long = sig["direction"] == "long"
        tick = self.mt5.symbol_info_tick(sym)
        price = tick.ask if is_long else tick.bid
        req = {
            "action": self.mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": lots,
            "type": self.mt5.ORDER_TYPE_BUY if is_long else self.mt5.ORDER_TYPE_SELL,
            "price": price, "sl": sig["stop"], "tp": sig["target"],
            "deviation": 20, "type_filling": self.mt5.ORDER_FILLING_IOC,
            "comment": "MSNR",
        }
        res = self.mt5.order_send(req)
        if not res or res.retcode != self.mt5.TRADE_RETCODE_DONE:
            return None
        return Position(id=str(res.order), pair=sig["pair"], tf=sig["tf"],
                        direction=sig["direction"], entry=price, stop=sig["stop"],
                        target=sig["target"], size=size, units=lots,
                        risk_amount=self.nav() * self.base_risk_pct * size,
                        open_time=str(sig["time"]), features=sig.get("features", {}))

    def sync(self) -> list[Position]:
        # SL/TP fill server-side; full closed-trade reconciliation via
        # history_deals_get() is broker-specific — left as a TODO for your broker.
        return []

"""Broker abstraction: a local PaperBroker (works now) and an OandaBroker (v20)."""
from src.broker.base import Broker, Position
from src.broker.paper import PaperBroker


def get_broker(kind: str = "paper", **kw) -> Broker:
    if kind == "paper":
        return PaperBroker(**kw)
    if kind == "mt5":
        from src.broker.mt5 import MT5Broker
        return MT5Broker(**kw)
    if kind == "oanda":
        from src.broker.oanda import OandaBroker
        return OandaBroker(**kw)
    raise ValueError(f"unknown broker {kind!r} (use 'paper', 'mt5' or 'oanda')")


__all__ = ["Broker", "Position", "PaperBroker", "get_broker"]

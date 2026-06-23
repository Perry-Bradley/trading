"""Broker interface + Position record shared by paper and live brokers."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Position:
    id: str
    pair: str
    tf: str
    direction: str          # "long" / "short"
    entry: float
    stop: float
    target: float
    size: float             # confidence size multiple
    units: float            # signed position size in units of base currency
    risk_amount: float      # account currency risked if stop hit
    open_time: str          # ISO timestamp of the trigger bar
    features: dict = field(default_factory=dict)   # for continual learning on close
    status: str = "open"
    exit: float | None = None
    exit_time: str | None = None
    outcome: str | None = None      # "win" / "loss"
    pnl: float = 0.0                # realised account-currency P&L
    r: float | None = None          # realised R

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        return cls(**d)


class Broker:
    """Minimal interface the trading engine depends on."""

    name = "base"

    def nav(self) -> float:
        raise NotImplementedError

    def open_positions(self) -> list[Position]:
        raise NotImplementedError

    def has_open(self, pair: str) -> bool:
        return any(p.pair == pair for p in self.open_positions())

    def open_trade(self, sig: dict, size: float) -> Position | None:
        raise NotImplementedError

    def sync(self) -> list[Position]:
        """Resolve/close trades; return the positions that closed this call."""
        raise NotImplementedError

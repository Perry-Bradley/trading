"""The trading engine tick — one cycle of the live/paper loop.

Each tick:
  1. sync the broker -> close any resolved trades
  2. LEARN: for every just-closed trade, partial_fit the online policy on its
     real outcome, then persist the updated policy   <-- continuous learning
  3. scan all pairs for fresh setups
  4. score each with the (now-updated) policy; open the confident ones
  5. alert on every close and every new entry

This is the loop that makes the deployed platform "keep learning like RL": the
model that decides tomorrow's trades is shaped by how today's trades actually
turned out. Run it on a schedule (cron / Railway worker / the /loop skill).
"""
from __future__ import annotations

import config
from src import backtest
from src.broker import get_broker
from src.ml.online import OnlinePolicy, policy_path, vec
from src.notify import notify


def tick(broker_kind: str = "paper", tf: str = "H4", bias_tf: str = "D1",
         target_r: float = 2.0, min_conf: float | None = None,
         lookback: int = 3, refresh: bool = False) -> dict:
    if refresh:
        from src.data import fetch
        for pr in config.PAIRS:
            for t in {tf, bias_tf}:
                try:
                    fetch.save(pr, t)
                except Exception as e:  # noqa: BLE001
                    print(f"  (refresh {pr} {t} failed: {e})")

    policy = OnlinePolicy.load_or_bootstrap(target_r)
    breakeven = 1.0 / (1.0 + target_r)
    min_conf = breakeven if min_conf is None else min_conf
    broker = get_broker(broker_kind, base_risk_pct=0.01)

    # 1+2. resolve closed trades and LEARN from each one
    learned = 0
    closed = broker.sync()
    for pos in closed:
        notify(f"CLOSED {pos.pair} {pos.direction} [{pos.outcome}]",
               f"P&L {pos.pnl:+.2f} (R {pos.r if pos.r is not None else 0:+.2f})  NAV {broker.nav():.2f}")
        if pos.features:
            policy.update(vec(pos.features), 1 if pos.outcome == "win" else 0)
            learned += 1
    if learned:
        policy.save(policy_path(target_r))

    # 3+4. scan, score with the updated policy, open confident setups
    opened = []
    for pr in config.PAIRS:
        try:
            sigs = backtest.signals(pr, tf, bias_tf, target_r, lookback=lookback)
        except FileNotFoundError:
            continue
        for s in sigs:
            p = policy.proba(vec(s["features"]))
            size = policy.size(p)
            s["conf"], s["size"] = p, size
            if p >= min_conf and size > 0 and not broker.has_open(pr):
                pos = broker.open_trade(s, size)
                if pos:
                    opened.append(s)
                    notify(f"NEW {pr} {s['direction'].upper()} {tf}/{bias_tf}",
                           f"entry {s['entry']:.5f} SL {s['stop']:.5f} TP {s['target']:.5f} "
                           f"1:{target_r:.0f}  conf {p*100:.1f}%  size {size:.2f}x")

    return {
        "broker": broker.name, "nav": broker.nav(), "target_r": target_r,
        "breakeven": breakeven, "n_updates": policy.n_updates,
        "closed": [c.to_dict() for c in closed],
        "opened": opened,
        "open_positions": [p.to_dict() for p in broker.open_positions()],
    }


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Run one trading-engine tick.")
    p.add_argument("--broker", default="paper", choices=["paper", "mt5", "oanda"])
    p.add_argument("--tf", default="H4"); p.add_argument("--bias-tf", default="D1")
    p.add_argument("--target-r", type=float, default=2.0)
    p.add_argument("--min-conf", type=float, default=None)
    p.add_argument("--refresh", action="store_true")
    a = p.parse_args()
    st = tick(a.broker, a.tf, a.bias_tf, a.target_r, a.min_conf, refresh=a.refresh)
    print(f"\n[{st['broker']}] NAV {st['nav']:.2f} | learned-from {st['n_updates']} trades | "
          f"{len(st['open_positions'])} open | {len(st['opened'])} new | {len(st['closed'])} closed")
    for pos in st["open_positions"]:
        print(f"  OPEN {pos['pair']:7} {pos['direction']:5} entry {pos['entry']:.5f} "
              f"SL {pos['stop']:.5f} TP {pos['target']:.5f} size {pos['size']:.2f}x")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

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

import datetime as _dt

import config
from src import backtest, journal
from src.broker import get_broker
from src.ml.online import OnlinePolicy, policy_path, vec
from src.notify import notify


def tick(broker_kind: str = "paper", tf: str = "H4", bias_tf: str = "D1",
         target_r: float = 2.0, min_conf: float | None = None,
         lookback: int = 3, refresh: bool = False) -> dict:
    # Auto-seed: on a fresh deploy there's no committed data, so the first tick
    # must fetch before it can bootstrap the model.
    have_data = ((config.DATA_DIR / f"{config.PAIRS[0]}_{tf}.parquet").exists()
                 and (config.DATA_DIR / f"{config.PAIRS[0]}_{bias_tf}.parquet").exists())
    if refresh or not have_data:
        from src.data import fetch
        for pr in config.PAIRS:
            for t in {"H4", "H1", "M30", tf, bias_tf}:
                try:
                    fetch.save(pr, t)
                except Exception as e:  # noqa: BLE001
                    print(f"  (fetch {pr} {t} failed: {e})")

    policy = OnlinePolicy.load_or_bootstrap(target_r)
    breakeven = 1.0 / (1.0 + target_r)
    broker = get_broker(broker_kind, base_risk_pct=0.01)
    # Paper: trade every eligible setup so journal + model accumulate learning data fast.
    if min_conf is None:
        min_conf = 0.0 if broker.name == "paper" else breakeven

    # --- resolve finished trades and LEARN from each (the RL feedback loop) ---
    closed_all: list = []

    def _process_closes(quiet: bool = False) -> None:
        learned = 0
        for pos in broker.sync():
            closed_all.append(pos)
            if not quiet:
                notify(f"CLOSED {pos.pair} {pos.direction} [{pos.outcome}]",
                       f"P&L {pos.pnl:+.2f} (R {pos.r if pos.r is not None else 0:+.2f})  "
                       f"NAV {broker.nav():.2f}")
            journal.record({"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                            "event": "CLOSE", "pair": pos.pair, "direction": pos.direction,
                            "tf": pos.tf, "entry": pos.entry, "stop": pos.stop, "target": pos.target,
                            "outcome": pos.outcome, "r": pos.r, "pnl": pos.pnl, "nav": broker.nav()})
            if pos.features:
                policy.update(vec(pos.features), 1 if pos.outcome == "win" else 0)
                learned += 1
        if learned:
            policy.save(policy_path(target_r))

    _process_closes()                       # genuine recent closes -> alert

    # --- scan a wide recent window and TEST every confident signal ---
    # paper tests EVERY distinct signal (accuracy reflects all predictions, not one
    # per pair); live brokers stay one-per-pair to avoid over-trading.
    opened = []
    scan_lookback = max(lookback, 48)
    entry_tfs = ["H4", "H1", "M30"] if broker.name == "paper" else [tf]
    from src.data.fetch import load
    from src.signal_filter import paper_eligible

    if broker.name == "paper" and hasattr(broker, "reconcile_with_journal"):
        broker.reconcile_with_journal()

    stats = {"signals_seen": 0, "eligible": 0, "conf_pass": 0, "blocked_dup": 0}
    for pr in config.PAIRS:
        for t in entry_tfs:
            try:
                df = load(pr, t)
                sigs = backtest.signals(pr, t, bias_tf, target_r, lookback=scan_lookback)
            except FileNotFoundError:
                continue
            for s in sigs:
                stats["signals_seen"] += 1
                if not paper_eligible(s, df, t):
                    continue
                stats["eligible"] += 1
                p = policy.proba(vec(s["features"]))
                if broker.name == "paper":
                    size = 1.0
                else:
                    size = policy.size(p)
                s["conf"], s["size"] = p, size
                gate = broker.name == "paper" or not broker.has_open(pr)
                if broker.name != "paper" and (p < min_conf or size <= 0 or not gate):
                    continue
                if broker.name == "paper" and not gate:
                    continue
                stats["conf_pass"] += 1
                pos = broker.open_trade(s, size)
                if not pos:
                    stats["blocked_dup"] += 1
                    continue
                opened.append(s)
                journal.record({"ts": _dt.datetime.now().isoformat(timespec="seconds"),
                                "event": "ENTRY", "pair": pr, "direction": s["direction"],
                                "tf": t, "entry": s["entry"], "stop": s["stop"],
                                "target": s["target"], "conf": round(p, 3),
                                "size": round(size, 2), "nav": broker.nav()})
                if s.get("age_bars", 99) <= 1:   # only alert on genuinely fresh signals
                    notify(f"NEW {pr} {s['direction'].upper()} {t}/{bias_tf}",
                           f"entry {s['entry']:.5f} SL {s['stop']:.5f} TP {s['target']:.5f} "
                           f"1:{target_r:.0f}  conf {p*100:.1f}%  size {size:.2f}x")

    _process_closes(quiet=True)             # resolve the just-opened historical signals now

    closed = closed_all
    rec = journal.track_record()
    if closed:
        notify("PROGRESS", f"{len(closed)} closed | NAV {broker.nav():.2f} | record: "
               + journal.summary_line())

    stats["journal_rows"] = journal.count()
    stats["paper_closed"] = len(getattr(broker, "state", {}).get("closed", []))
    return {
        "broker": broker.name, "nav": broker.nav(), "target_r": target_r,
        "breakeven": breakeven, "n_updates": policy.n_updates,
        "track_record": rec,
        "closed": [c.to_dict() for c in closed],
        "opened": opened,
        "open_positions": [p.to_dict() for p in broker.open_positions()],
        "tick_stats": stats,
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

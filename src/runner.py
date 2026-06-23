"""Scheduler — run engine ticks on a fixed interval (local machine / VPS).

    python -m src.runner --interval 3600            # tick hourly (paper)
    python -m src.runner --interval 14400 --tf H4   # every 4h, aligned-ish to H4

On Railway, prefer a separate **cron service** that hits the API instead of
running this loop, e.g.:  curl -X POST "$API_URL/api/tick?refresh=1"
"""
from __future__ import annotations

import argparse
import time

from src import engine


def main() -> int:
    p = argparse.ArgumentParser(description="Interval scheduler for engine ticks.")
    p.add_argument("--interval", type=int, default=3600, help="seconds between ticks")
    p.add_argument("--broker", default="paper", choices=["paper", "mt5", "oanda"])
    p.add_argument("--tf", default="H4")
    p.add_argument("--bias-tf", default="D1")
    p.add_argument("--target-r", type=float, default=2.0)
    p.add_argument("--no-refresh", action="store_true", help="don't re-pull data each tick")
    a = p.parse_args()

    print(f"runner: tick every {a.interval}s on {a.tf}/{a.bias_tf} via {a.broker} "
          f"(refresh={'off' if a.no_refresh else 'on'}). Ctrl-C to stop.")
    while True:
        try:
            st = engine.tick(a.broker, a.tf, a.bias_tf, a.target_r, refresh=not a.no_refresh)
            tr = st.get("track_record", {})
            print(f"  tick @ {st.get('when','')} | NAV {st['nav']:.2f} | "
                  f"{len(st['open_positions'])} open | {len(st['opened'])} new | "
                  f"{len(st['closed'])} closed | learned {st['n_updates']} | "
                  f"record {tr.get('wins',0)}/{tr.get('resolved',0)}")
        except Exception as e:  # noqa: BLE001
            print("  tick error:", e)
        time.sleep(max(60, a.interval))


if __name__ == "__main__":
    import sys
    sys.exit(main())

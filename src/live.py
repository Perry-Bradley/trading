"""Live MSNR signal monitor.

Pulls the latest data, finds setups that have triggered on the most recent bars,
scores each with the trained ML filter, and prints a clean signal: direction,
entry, stop-loss, take-profit, R:R, model confidence and suggested size.

  python -m src.live                      # scan cached data (H4 entry / D1 bias)
  python -m src.live --refresh            # re-download latest bars first
  python -m src.live --tf H4 --bias-tf D1 --target-r 2 --min-conf 0.40

DATA NOTE: by default this uses the same yfinance data as the rest of the project
(free, no key, but delayed ~15 min and limited intraday history). For true live
streaming, point `src/data/fetch.py` at a broker API — see README "Live data".

This is decision-support, NOT financial advice or an auto-trader. Paper-trade first.
"""
from __future__ import annotations

import argparse

import joblib
import numpy as np

import config
from src import backtest
from src.data import fetch
from src.ml.dataset import FEATURES


def _load_model(target_r: float):
    path = config.MODELS_DIR / f"msnr_filter_{int(target_r)}r.joblib"
    if not path.exists():
        return None
    return joblib.load(path)


def _size(p: float, target_r: float, gain: float = 10.0, max_size: float = 2.5) -> float:
    be = 1.0 / (1.0 + target_r)
    return float(np.clip((p - be) * gain, 0.0, max_size)) if p > be else 0.0


def run(tf: str, bias_tf: str, target_r: float, lookback: int, min_conf: float,
        refresh: bool) -> None:
    if refresh:
        print("Refreshing latest data...")
        for pr in config.PAIRS:
            for t in {tf, bias_tf}:
                try:
                    fetch.save(pr, t)
                except Exception as e:  # noqa: BLE001
                    print(f"  (refresh {pr} {t} failed: {e})")
        print()

    model = _load_model(target_r)
    be = 1.0 / (1.0 + target_r)
    print(f"LIVE MSNR signals | {tf} entry / {bias_tf} bias | target {target_r}R | "
          f"breakeven {be*100:.1f}%")
    print(f"model: {'loaded' if model else 'NONE (run `python -m src.ml.train '+str(int(target_r))+'` first)'}\n")

    found = []
    for pr in config.PAIRS:
        try:
            sigs = backtest.signals(pr, tf, bias_tf, target_r, lookback=lookback)
        except FileNotFoundError:
            continue
        for s in sigs:
            if model:
                x = np.array([[s["features"][f] for f in FEATURES]], dtype=float)
                p = float(model["pipeline"].predict_proba(x)[0, 1])
            else:
                p = float("nan")
            s["conf"], s["size"] = p, _size(p, target_r)
            found.append(s)

    # show highest-confidence first
    found.sort(key=lambda s: (-(s["conf"] if s["conf"] == s["conf"] else -1)))
    shown = 0
    for s in found:
        conf_ok = (s["conf"] != s["conf"]) or (s["conf"] >= min_conf)  # nan => show
        if not conf_ok:
            continue
        shown += 1
        tag = "TAKE " if (s["conf"] == s["conf"] and s["conf"] > be and s["size"] > 0) else "watch"
        conf = "n/a" if s["conf"] != s["conf"] else f"{s['conf']*100:4.1f}%"
        print(f"  [{tag}] {s['pair']:7} {s['direction'].upper():5} {s['tf']}/{s['bias_tf']}  "
              f"{s['time']:%Y-%m-%d %H:%M}")
        print(f"          entry {s['entry']:.5f}  SL {s['stop']:.5f}  TP {s['target']:.5f}  "
              f"R:R 1:{s['rr']:.0f}  conf {conf}  size {s['size']:.2f}x")
    if not shown:
        print("  No fresh setups on the latest bars.")
    print(f"\n  {shown} signal(s). 'TAKE' = model confidence above breakeven; 'watch' = "
          "triggered but sub-edge.")
    print("  Reminder: decision-support only. Paper-trade before risking real capital.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Live MSNR signal monitor.")
    p.add_argument("--tf", default="H4", choices=list(config.TIMEFRAMES))
    p.add_argument("--bias-tf", default="D1", choices=list(config.TIMEFRAMES))
    p.add_argument("--target-r", type=float, default=2.0)
    p.add_argument("--lookback", type=int, default=3, help="bars from the right edge to scan")
    p.add_argument("--min-conf", type=float, default=0.0)
    p.add_argument("--refresh", action="store_true", help="re-download latest bars first")
    args = p.parse_args(argv)
    run(args.tf, args.bias_tf, args.target_r, args.lookback, args.min_conf, args.refresh)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

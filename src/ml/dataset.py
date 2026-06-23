"""Build a pooled, labelled dataset of MSNR setups for the ML filter.

Each row is one trade the backtester actually took, with:
  * causal features captured at the entry bar (no lookahead),
  * the realised outcome (`win` = 1 if it hit target, else 0),
  * the realised `r` (for evaluating expectancy of any filtered subset),
  * `pair` and `entry_time` (the latter drives the time-based split).

The label and the economics come straight from the same causal backtest engine,
so the dataset can never disagree with the strategy it is meant to filter.
"""
from __future__ import annotations

import pandas as pd

import config
from src import backtest


# Minutes-per-bar for the timeframe feature (lets the model tell H4 from D1 setups).
TF_MINUTES = {"M30": 30, "H1": 60, "H4": 240, "D1": 1440}

# (entry_tf, bias_tf) configs to pool — uses as much data as we have:
# H4 entries with D1 bias (~2.8y) PLUS D1 entries with same-TF bias (~20y).
DEFAULT_CONFIGS = [("H4", "D1"), ("D1", "D1")]


def build(target_r: float = 2.0, configs: list[tuple[str, str]] | None = None,
          pairs: list[str] | None = None) -> pd.DataFrame:
    pairs = pairs or config.PAIRS
    configs = configs or DEFAULT_CONFIGS
    rows = []
    for tf, bias_tf in configs:
        for pair in pairs:
            try:
                m = backtest.run(pair, tf, bias_tf, target_r=target_r, collect_features=True)
            except FileNotFoundError:
                continue
            for t in m["_trades"]:
                row = dict(t.features)
                row.update({
                    "pair": pair, "tf": tf, "tf_minutes": TF_MINUTES[tf],
                    "entry_time": t.entry_time,
                    "direction": 1 if t.direction == "long" else 0,
                    "r": t.r,
                    "win": 1 if t.outcome == "win" else 0,
                })
                rows.append(row)
    df = pd.DataFrame(rows).sort_values("entry_time").reset_index(drop=True)
    return df


FEATURES = [
    "rej_strength", "zone_width_atr", "zone_age", "depth_atr", "atr_regime",
    "choch_recent", "sweep_recent", "ob_conf", "fvg_conf", "trend_age",
    "hour", "dow", "direction", "tf_minutes",
]


if __name__ == "__main__":
    import sys
    tr = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    d = build(target_r=tr)
    print(f"dataset: {len(d)} setups, win rate {d['win'].mean()*100:.1f}%")
    print(d[["entry_time", "pair", "win", "r"] + FEATURES].head(8).to_string())
    print("\nwin rate by pair:")
    print((d.groupby("pair")["win"].mean() * 100).round(1).to_string())

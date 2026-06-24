"""Full 3-TF signal audit - shows what the dashboard will see after fix."""
import config
from src import backtest

_TF_MAX_AGE = {"H4": 6, "H1": 6, "M30": 8}
_ENTRY_TFS = ["H4", "H1", "M30"]

totals = {"H4": 0, "H1": 0, "M30": 0}
print("=" * 65)
print(f"{'PAIR':<10} {'TF':<5} {'DIR':<6} {'ENTRY':>10} {'R:R':>6} {'AGE':>5}")
print("=" * 65)

for pr in config.PAIRS:
    for tf in _ENTRY_TFS:
        try:
            max_age = _TF_MAX_AGE[tf]
            sigs = backtest.signals(pr, tf, "D1", 2.0, lookback=max_age + 4)
            fresh = [s for s in sigs if s.get("age_bars", 999) <= max_age]
            for s in fresh:
                totals[tf] += 1
                print(f"{pr:<10} {tf:<5} {s['direction']:<6} {s['entry']:>10.5f} {s['rr']:>6.2f}R  {s['age_bars']} bars ago")
        except Exception as e:
            pass  # pair has no data

print("=" * 65)
print(f"TOTAL: H4={totals['H4']}  H1={totals['H1']}  M30={totals['M30']}  (Grand total: {sum(totals.values())})")
print("Note: correlation filter in app.py will pick best 1 per group.")

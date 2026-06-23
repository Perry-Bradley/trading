"""Train and HONESTLY evaluate the MSNR setup filter.

The question this answers: if we let a model keep only its higher-confidence
setups, does out-of-sample **expectancy** improve? Not accuracy — expectancy.

Anti-fool-yourself rules enforced here:
  * Time-based split: train on the earliest 70% of trades, test on the last 30%.
    No random shuffling (that leaks the future into the past on a time series).
  * Thresholds are chosen on TRAIN only (as probability quantiles), then applied
    unchanged to TEST. We never pick a threshold by peeking at test results.
  * Headline metric is cross-validated AUC (TimeSeriesSplit) — a single lucky
    split proves nothing on ~300 samples.
  * Sample size is small; results are reported with that caveat, loudly.

Usage:
    python -m src.ml.train            # 2R dataset
    python -m src.ml.train 3          # 3R dataset
"""
from __future__ import annotations

import sys

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.ml.dataset import FEATURES, build


def _econ(r: np.ndarray) -> str:
    n = len(r)
    if n == 0:
        return "   0 trades"
    win = (r > 0).mean() * 100
    return f"{n:4d} trades  win {win:5.1f}%  exp {r.mean():+.3f}R  total {r.sum():+7.1f}R"


def main() -> int:
    target_r = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    df = build(target_r=target_r)
    X = df[FEATURES].to_numpy(dtype=float)
    y = df["win"].to_numpy(dtype=int)
    r = df["r"].to_numpy(dtype=float)
    n = len(df)
    print(f"=== MSNR ML filter | target {target_r}R | {n} setups | base win {y.mean()*100:.1f}% ===\n")

    # ---- cross-validated AUC (the honest headline) ----
    lr = Pipeline([("sc", StandardScaler()),
                   ("lr", LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000))])
    gb = HistGradientBoostingClassifier(max_depth=2, max_iter=120, learning_rate=0.05,
                                        l2_regularization=1.0, random_state=0)
    tscv = TimeSeriesSplit(n_splits=5)
    for name, model in [("LogReg", lr), ("HistGBM", gb)]:
        aucs = []
        for tr, te in tscv.split(X):
            if len(np.unique(y[tr])) < 2:
                continue
            model.fit(X[tr], y[tr])
            p = model.predict_proba(X[te])[:, 1]
            if len(np.unique(y[te])) > 1:
                aucs.append(roc_auc_score(y[te], p))
        aucs = np.array(aucs)
        flag = "signal" if aucs.mean() > 0.55 else ("weak" if aucs.mean() > 0.52 else "~none")
        print(f"  {name:7} CV AUC {aucs.mean():.3f} +/- {aucs.std():.3f}   ({flag})")

    # ---- time-based holdout: train 70% / test 30% ----
    cut = int(n * 0.70)
    Xtr, Xte, ytr, rte = X[:cut], X[cut:], y[:cut], r[cut:]
    rtr = r[:cut]
    lr.fit(Xtr, ytr)
    ptr, pte = lr.predict_proba(Xtr)[:, 1], lr.predict_proba(Xte)[:, 1]
    test_auc = roc_auc_score(y[cut:], pte) if len(np.unique(y[cut:])) > 1 else float("nan")

    print(f"\n  Holdout: train {cut} / test {n-cut} setups   (LogReg test AUC {test_auc:.3f})")
    print(f"  TEST unfiltered : {_econ(rte)}")
    print(f"  (TRAIN unfiltered: {_econ(rtr)})\n")

    # thresholds set on TRAIN as probability quantiles, applied unchanged to TEST
    print("  Keep top-X% most-confident setups (threshold from TRAIN, economics on TEST):")
    for frac in (0.75, 0.50, 0.33):
        thr = np.quantile(ptr, 1 - frac)
        keep = pte >= thr
        print(f"    top {int(frac*100):3d}% (P>={thr:.2f}) : {_econ(rte[keep])}")

    # ---- coefficients (what the model leans on) ----
    coefs = lr.named_steps["lr"].coef_[0]
    order = np.argsort(np.abs(coefs))[::-1]
    print("\n  LogReg drivers (standardised coef, + = more likely to win):")
    for k in order[:8]:
        print(f"    {FEATURES[k]:16} {coefs[k]:+.3f}")

    print("\n  NOTE: ~300 trades is a SMALL sample. Treat a positive result as "
          "'worth more data', not proof. Out-of-sample AUC near 0.50 means no edge.")

    # ---- persist a model fit on ALL data for the scanner to use (Phase 5 hook) ----
    import config
    lr.fit(X, y)
    keep_thr = float(np.quantile(lr.predict_proba(X)[:, 1], 0.50))  # keep top ~50%
    models_dir = config.ROOT / "models"
    models_dir.mkdir(exist_ok=True)
    out = models_dir / f"msnr_filter_{int(target_r)}r.joblib"
    joblib.dump({"pipeline": lr, "features": FEATURES, "threshold": keep_thr,
                 "target_r": target_r, "cv_auc": float(aucs.mean())}, out)
    print(f"  saved model -> {out.name}  (keep setups with P(win) >= {keep_thr:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

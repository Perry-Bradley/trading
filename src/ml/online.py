"""Online contextual-bandit policy — the 'RL that keeps learning' layer.

Framing (the right form of RL for this data scale):
  * context = a setup's causal features
  * action  = skip, or take with a confidence-scaled size
  * reward  = realised R (so the policy directly optimises expectancy)

It is a ONE-STEP RL problem (a contextual bandit), which is far more data-efficient
and robust than full sequential deep RL on noisy, non-stationary price data.

Continual learning is real here: a `SGDClassifier` (log-loss) is warm-started on
historical setups (the foundation) and then `partial_fit`-updated after every new
trade resolves — exactly "train on past, keep learning". The feature scaler is fit
ONCE on the warmup window and frozen, so online updates never peek at the future.

Sizing: above the break-even win rate (1/(1+R)) the policy scales size with the
model's edge (a fractional-Kelly-style heuristic), so confident, high-R:R setups
get more; marginal ones get little; sub-break-even setups are skipped entirely.

Usage:
    python -m src.ml.online            # 2R, pooled H4+D1 dataset
    python -m src.ml.online 3 150      # target 3R, 150-trade warmup
"""
from __future__ import annotations

import sys

import joblib
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight

import config
from src.ml.dataset import FEATURES, build


def vec(features: dict) -> np.ndarray:
    """Turn a feature dict into the model's input vector (FEATURES order)."""
    return np.array([features.get(f, 0.0) for f in FEATURES], dtype=float)


def policy_path(target_r: float):
    return config.ROOT / "models" / f"online_policy_{int(target_r)}r.joblib"


class OnlinePolicy:
    def __init__(self, target_r: float, gain: float = 10.0, max_size: float = 2.5,
                 alpha: float = 1e-3, learning_rate: str = "optimal", eta0: float = 0.0):
        # learning_rate: "optimal" (default, decays with #updates — stable, slow to
        #   adapt) or "constant" with eta0>0 (each new trade has steady influence —
        #   faster regime adaptation, noisier). See env LEARNING_RATE / ETA0.
        self.target_r = target_r
        self.breakeven = 1.0 / (1.0 + target_r)
        self.gain = gain
        self.max_size = max_size
        self.scaler = StandardScaler()
        self.clf = SGDClassifier(loss="log_loss", alpha=alpha,
                                 learning_rate=learning_rate, eta0=eta0, random_state=0)
        self.cw = {0: 1.0, 1: 1.0}
        self.n_updates = 0          # how many live trades it has learned from
        self._ready = False

    def warmup(self, X: np.ndarray, y: np.ndarray, epochs: int = 8) -> None:
        self.scaler.fit(X)
        Xs = self.scaler.transform(X)
        classes = np.array([0, 1])
        w = compute_class_weight("balanced", classes=classes, y=y)
        self.cw = {0: float(w[0]), 1: float(w[1])}          # balance classes manually
        sw = np.array([self.cw[v] for v in y])
        for _ in range(epochs):
            self.clf.partial_fit(Xs, y, classes=classes, sample_weight=sw)
        self._ready = True

    def proba(self, x: np.ndarray) -> float:
        xs = self.scaler.transform(x.reshape(1, -1))
        return float(self.clf.predict_proba(xs)[0, 1])

    def size(self, p: float) -> float:
        """Confidence-scaled position size (0 = skip)."""
        if p <= self.breakeven:
            return 0.0
        return float(np.clip((p - self.breakeven) * self.gain, 0.0, self.max_size))

    def update(self, x: np.ndarray, y: int) -> None:
        xs = self.scaler.transform(x.reshape(1, -1))
        self.clf.partial_fit(xs, np.array([y]), sample_weight=np.array([self.cw[y]]))
        self.n_updates += 1

    # --- persistence (so the policy lives & keeps learning in production) ---
    def save(self, path) -> None:
        joblib.dump({"scaler": self.scaler, "clf": self.clf, "cw": self.cw,
                     "target_r": self.target_r, "gain": self.gain,
                     "max_size": self.max_size, "n_updates": self.n_updates,
                     "ready": self._ready}, path)

    @classmethod
    def load(cls, path) -> "OnlinePolicy":
        d = joblib.load(path)
        p = cls(d["target_r"], gain=d["gain"], max_size=d["max_size"])
        p.scaler, p.clf, p.cw = d["scaler"], d["clf"], d["cw"]
        p.n_updates, p._ready = d.get("n_updates", 0), d.get("ready", True)
        return p

    @classmethod
    def bootstrap(cls, target_r: float = 2.0, save: bool = True, **kw) -> "OnlinePolicy":
        """Warm-start a fresh policy on ALL historical setups (the foundation)."""
        df = build(target_r=target_r)
        X = df[FEATURES].to_numpy(dtype=float)
        y = df["win"].to_numpy(dtype=int)
        pol = cls(target_r, **kw)
        pol.warmup(X, y)
        if save:
            policy_path(target_r).parent.mkdir(exist_ok=True)
            pol.save(policy_path(target_r))
        return pol

    @classmethod
    def load_or_bootstrap(cls, target_r: float = 2.0) -> "OnlinePolicy":
        p = policy_path(target_r)
        return cls.load(p) if p.exists() else cls.bootstrap(target_r)


def walk_forward(target_r: float = 2.0, warmup: int = 200, gain: float = 10.0,
                 max_size: float = 2.5) -> dict:
    df = build(target_r=target_r)
    X = df[FEATURES].to_numpy(dtype=float)
    y = df["win"].to_numpy(dtype=int)
    r = df["r"].to_numpy(dtype=float)
    n = len(df)
    if n <= warmup + 20:
        raise RuntimeError(f"not enough setups ({n}) for warmup={warmup}")

    pol = OnlinePolicy(target_r, gain=gain, max_size=max_size)
    pol.warmup(X[:warmup], y[:warmup])

    # walk forward over the held-out tail, learning online after each resolution
    online_r, taken_win, sizes = [], [], []
    baseline_r, eq_online_aligned = [], []     # aligned to the same chronological x-axis
    running = 0.0
    for i in range(warmup, n):
        p = pol.proba(X[i])
        s = pol.size(p)
        if s > 0:
            online_r.append(r[i] * s)
            taken_win.append(1 if r[i] > 0 else 0)
            sizes.append(s)
            running += r[i] * s
        baseline_r.append(r[i])
        eq_online_aligned.append(running)
        pol.update(X[i], y[i])             # <-- continual learning step

    online_r = np.array(online_r)
    baseline_r = np.array(baseline_r)
    eq_online = np.array(eq_online_aligned)
    eq_base = np.cumsum(baseline_r)

    # equity curve plot
    charts = config.ROOT / "charts"; charts.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(eq_base, label=f"take-all baseline ({len(baseline_r)} trades)", color="#90a4ae")
    ax.plot(eq_online, label=f"online policy ({len(online_r)} taken)", color="#1565c0", linewidth=2)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_title(f"Online bandit vs take-all  |  target {target_r}R  |  walk-forward (R units)")
    ax.set_xlabel("trade # (post-warmup, chronological)"); ax.set_ylabel("cumulative R")
    ax.legend(); ax.grid(alpha=0.15)
    out = charts / f"online_equity_{int(target_r)}r.png"
    fig.tight_layout(); fig.savefig(out, dpi=120); plt.close(fig)

    return {
        "target_r": target_r, "warmup": warmup, "n_total": n,
        "online_taken": len(online_r),
        "online_win": float(np.mean(taken_win)) if taken_win else 0.0,
        "online_total_r": float(online_r.sum()),
        "online_exp_r": float(online_r.mean()) if len(online_r) else 0.0,
        "avg_size": float(np.mean(sizes)) if sizes else 0.0,
        "baseline_n": len(baseline_r),
        "baseline_win": float((baseline_r > 0).mean()),
        "baseline_total_r": float(baseline_r.sum()),
        "baseline_exp_r": float(baseline_r.mean()),
        "chart": str(out),
    }


def main() -> int:
    target_r = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    warmup = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    m = walk_forward(target_r=target_r, warmup=warmup)
    print(f"=== Online bandit (continual learning) | target {target_r}R | "
          f"{m['n_total']} setups, warmup {warmup} ===\n")
    print(f"  Walk-forward tail: {m['baseline_n']} setups\n")
    print(f"  {'take-all baseline':22}: {m['baseline_n']:4d} trades  "
          f"win {m['baseline_win']*100:5.1f}%  exp {m['baseline_exp_r']:+.3f}R  "
          f"total {m['baseline_total_r']:+7.1f}R")
    print(f"  {'online policy (sized)':22}: {m['online_taken']:4d} trades  "
          f"win {m['online_win']*100:5.1f}%  exp {m['online_exp_r']:+.3f}R  "
          f"total {m['online_total_r']:+7.1f}R  (avg size {m['avg_size']:.2f}x)")
    lift = m["online_total_r"] - m["baseline_total_r"]
    print(f"\n  Online vs take-all: {lift:+.1f}R   (chart: {m['chart'].split(chr(92))[-1]})")
    print("\n  HONEST READ: walk-forward on historical data; each step the model learns "
          "from the\n  just-resolved trade. Small samples stay noisy — watch the trend, "
          "not the last point.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

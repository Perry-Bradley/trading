# MSNR Trading Assistant

A trading assistant that codifies the **EmperorFX Learn2Trade** curriculum —
Malaysian Support & Resistance (MSNR) combined with Smart Money Concepts (SMC) —
into automated detectors, a scanner, and a backtester.

## Philosophy

This is **not** a "predict price with 90% accuracy" project. The MSNR strategy is a
tight-stop, high-R:R approach, so profitability comes from **expectancy**, not win rate.
The goal is to:

1. Mechanically detect the setups the strategy already defines (the assistant part).
2. Backtest them to measure the **real** win rate, expectancy, and drawdown.
3. Layer ML on top to *rank/filter* setups — improving expectancy, not chasing accuracy.

## Build phases

- [x] **Phase 0 — Data**: pull historical forex OHLCV across the MSNR timeframe ladder.
- [x] **Phase 1 — Detectors**: market structure (HH/HL/LL/LH, BOS, CHoCH), SNR zones
  (fresh/unfresh/flip), rejection candles, order blocks, FVGs, liquidity sweeps.
- [x] **Phase 2 — Scanner**: combine detectors + multi-timeframe alignment → flag setups.
- [x] **Phase 3 — Backtester**: causal, costs baked in, R-multiples, expectancy/PF/drawdown.
- [x] **Phase 4 — ML layer**: causal features → regularized filter + **online contextual
  bandit** (continual learning) → confidence-scaled, high-R:R position sizing.
- [x] **Phase 5 — Assistant**: live signals, paper/MT5/OANDA brokers, alerts
  (console/log/Telegram), continual-learning engine, **JSON API + Next.js dashboard**,
  trade journal, scheduler, Railway deploy.

### Architecture (two services)

```
 Python backend  (src/)            Next.js frontend (web/)
 ────────────────────────          ───────────────────────
 detectors · scanner · backtest    SaaS dashboard, mobile-responsive
 ML + online bandit (learns)       polls the API, "Run tick" button
 brokers · journal · engine
 Flask JSON API  ───────────────►  fetch /api/* (NEXT_PUBLIC_API_URL)
```

### Run it locally
```bash
# 1) backend API
python -m src.webapp.app                 # http://localhost:8000  (/api/*)
# 2) frontend (separate terminal)
cd web && npm install && npm run dev      # http://localhost:3000
# 3) keep it ticking + learning on a schedule
python -m src.runner --interval 3600      # hourly: scan, trade, LEARN, alert
```

- **`src/engine.py`** `tick()` — sync broker → **learn from every closed trade
  (`partial_fit` + re-save)** → scan → score → open confident setups → journal + alert.
  The "keeps learning like RL" loop.
- **`src/journal.py`** — every entry/close logged to `data/journal.csv`; `track_record()`
  powers the dashboard's win-rate / expectancy / total-R panel.
- **Brokers** (`src/broker/`): `paper` (local, no account), `mt5` (Exness/Deriv/XM —
  **works in Cameroon**), `oanda`. **OANDA is not required.**
- **Alerts** (`src/notify.py`): console + `alerts.log` always; **Telegram** push if configured
  (`python -m src.notify "test"` to check).
- **Pairs (11)**: EUR/GBP/AUD/NZD-USD, USDJPY, USDCAD, EURNZD, EURJPY, GBPJPY, CHFJPY, BTCUSD
  — liquid majors + clean crosses (best structure adherence) + crypto.
- **Deploy:** see **[DEPLOY.md](DEPLOY.md)** (both services on Railway).

### Phase 4 — ML filter (honest evaluation)

`src/ml/` builds a pooled, labelled dataset (one row per backtest trade, causal
features at entry) and trains a regularized logistic-regression filter. Evaluation
is deliberately strict: time-based 70/30 split, thresholds chosen on TRAIN only,
headline metric is **cross-validated AUC** (`TimeSeriesSplit`).

Result at 2R (`python -m src.ml.train 2`):

- **CV AUC ≈ 0.55** (LogReg) — a *weak but consistent* signal; HistGBM ≈ 0.52 (none → simple model wins on small data).
- On the (losing) test slice, keeping the model's **top-50% most-confident** setups turned −6.7R into **+2.6R** and lifted win rate 32.6% → 37.1% (>33.3% breakeven). Modest, out-of-sample, in the right direction.
- Sensible drivers: deeper wick rejection (`depth_atr`), mature trend (`trend_age`), stronger rejection candle, time-of-day — i.e. it leans on real strategy logic, not noise.

> ~300 trades is a **small** sample. This is "promising, get more data" — not a proven edge. The honest bottleneck is data quantity (see Yahoo intraday limits).

### Online learning (the "RL that keeps learning")

`src/ml/online.py` is a **contextual bandit** (the data-efficient, one-step form of RL —
deliberately *not* full deep RL, which overfits hopelessly at this data scale). It
warm-starts on history, then `partial_fit`-updates after every resolved trade, and
sizes positions by confidence (fractional-Kelly-style). Pooling H4 + 20y of D1 gives
**1,134 setups**.

Walk-forward (warmup 200, then learning online over 934 setups, 2R):

| Policy | Trades | Win % | Total R |
|--------|--------|-------|---------|
| take-all baseline | 934 | 32.7 | **−111.5R** |
| online policy (sized) | 479 | 37.6 | **+19.1R** |

The learned policy skips ~half the setups and flips a clearly-losing take-all into
positive — see `charts/online_equity_2r.png`. **Caveats:** the per-setup signal is
weak (batch CV AUC ≈ 0.52), the curve is volatile with real drawdowns, and avg size
2.3× is aggressive (≈2.3% risk/trade — above the 1–2% rule; tune `gain`/`max_size`).

### Baseline backtest (H4 entry / D1 bias, 6 pairs, ~2.8y intraday, costs ON)

First-pass, **untuned** numbers from `python -m src.backtest`:

| Target | Trades | Win% | Breakeven% | Total R |
|--------|--------|------|------------|---------|
| 2R     | 295    | 36.6 | 33.3       | **+18.8R** |
| 3R     | 285    | 24.2 | 25.0       | −11.5R |
| 5R     | 272    | 13.2 | 16.7       | −11.1R |

Read this honestly: the raw model has a **small but real positive edge at the 2R
target** (win rate clears breakeven with margin), and is roughly breakeven at 3R.
This is exactly the expectancy-not-accuracy picture — no 90% anything. The 2R
result still needs out-of-sample / per-pair robustness checks before being trusted
(don't just pick the best-looking parameter). The backtester is the tool for that.

> **Tuning note:** the detector *thresholds* (swing sensitivity `left/right`, SNR
> zone width `buffer_atr`, rejection `wick_frac`, displacement `mult`, scanner
> `near_atr`) are first-pass defaults. They are meant to be tuned against your eye
> and, later, against backtest results — that's Phase 3's job.

## Layout

```
trading/
  config.py                  # pairs, timeframes, pip sizes, paths
  requirements.txt
  src/
    data/fetch.py            # OHLCV downloader + load()
    detectors/
      candles.py             # body/wick/ATR/displacement helpers
      structure.py           # swings, HH/HL/LL/LH, BOS, CHoCH
      snr.py                 # MSNR support/resistance zones (fresh/flip)
      rejection.py           # rejection / pin-bar candles
      smc.py                 # order blocks, fair value gaps, liquidity sweeps
    scanner.py               # Phase 2: combine detectors -> live setups
    viz/
      plot_structure.py      # structure-only chart
      plot_chart.py          # full chart: zones + structure + rejections
  data/                      # downloaded parquet — not committed
  charts/                    # rendered PNGs — not committed
  _lessons_text/             # extracted course notes (reference)
```

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 1. get data (all pairs x all timeframes)
python -m src.data.fetch --all

# 2. scan for live MSNR setups
python -m src.scanner --htf H4 --ltf H1        # all pairs
python -m src.scanner --htf D1 --ltf H4        # daily bias, H4 entry

# 3. render an annotated chart
python -m src.viz.plot_chart --pair AUDUSD --timeframe D1 --bars 130

# 4. backtest the model (honest: causal, costs baked in, R-multiples)
python -m src.backtest --tf H4 --bias-tf D1 --target-r 2

# 5. train the ML filter + online bandit (continual learning)
python -m src.ml.train 2            # batch filter + honest CV/holdout
python -m src.ml.online 2 200       # online policy, walk-forward, equity chart

# 6. live signals (entry / SL / TP / confidence / size)
python -m src.live --tf H4 --bias-tf D1 --target-r 2 --refresh
```

## Live data

`src/live.py` defaults to the project's yfinance data — free, no key, but **delayed
~15 min** with limited intraday history. Fine for H4/D1 swing signals; not for
seconds-level entries. For true live data, point `src/data/fetch.py` at one of:

| Provider | Best for | Cost | Notes |
|----------|----------|------|-------|
| **OANDA v20** | forex | free practice acct | REST + streaming, clean Python; recommended for the FX pairs |
| **MetaTrader 5** (`MetaTrader5` pkg) | forex + more | free w/ broker demo | real-time + deep history; Windows-friendly |
| **Binance API** | BTCUSD / crypto | free | excellent granular history + websockets |
| Polygon / Twelve Data / Finnhub | multi-asset | free tier | REST, good for daily/intraday pulls |

The data layer is abstracted behind `fetch.load(pair, tf)`, so swapping the source
is a localized change — the detectors, scanner, backtester and ML all stay as-is.

## Course source material

Strategy rules are codified from two course sets, extracted to text under
`_lessons_text/` (EmperorFX) and `_course_v2/` (JETFX 20-part course). The
detectors follow JETFX Module 06 (market structure) and 17 (MSNR); the backtester's
risk model follows Modules 05 & 15 (risk / money-management: R-multiples, costs,
≥3:1 R:R, drawdown math).

## Using the detectors directly

```python
import pandas as pd
from src.data.fetch import load
from src.detectors import structure, snr, rejection, smc

df = load("EURUSD", "H4")
st  = structure.analyze(df)          # {"swings": [...], "breaks": [...]}
zones = snr.detect(df)               # [SNRZone(kind, top, bottom, fresh?, flipped?), ...]
fresh = snr.fresh_zones_at(zones, len(df)-1)
rej = rejection.detect(df)           # DataFrame: bull_rej / bear_rej / strength
obs = smc.order_blocks(df)           # [Zone(...)]
fvgs = smc.fair_value_gaps(df)
sweeps = smc.liquidity_sweeps(df)    # [Sweep(direction, level, ...)]
```

## Data note

The proof-of-concept uses [yfinance](https://github.com/ranaroussi/yfinance) (free, no key).
Yahoo's intraday history is limited (≈730 days for 1h, ≈60 days for 30m), so for serious
H4/H1/M30 backtesting we'll later swap in a higher-quality source (e.g. Dukascopy).

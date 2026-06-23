# Deploying the MSNR Assistant

## What runs where

- **Locally / on Railway with NO broker account:** paper-trading, signals, the
  dashboard, and continuous learning all work with the free `paper` broker and
  yfinance data. You need *nothing* external to start.
- **Real execution (demo or live):** plug in a broker. The broker layer is
  pluggable (`src/broker/`), so you are **not tied to OANDA**.

## Brokers (pick what's available in your country)

| Broker | Account needed | Good for | Cameroon? |
|--------|----------------|----------|-----------|
| `paper` | none | testing, learning, signals | ✅ always |
| `mt5` (Exness, Deriv, XM, FBS, HFM) | broker demo/live + MT5 terminal | forex + more | ✅ yes — **recommended** (you're on Windows) |
| Binance | free API keys | BTCUSD / crypto | ✅ yes |
| `oanda` | v20 token | forex | ❌ restricted in many African countries |

> **You don't need OANDA.** For forex from Cameroon, open a demo with an
> MT5 broker that accepts you (Exness/Deriv/XM are popular there), install their
> MT5 terminal, then use `--broker mt5`. For crypto, Binance works globally.

### MT5 setup (Windows)
```
pip install MetaTrader5
# install your broker's MT5 terminal, log into the demo account
# (optional) set MT5_LOGIN / MT5_PASSWORD / MT5_SERVER, and MT5_SUFFIX if symbols
#            look like "EURUSD.m"
python -m src.engine --broker mt5 --refresh
```

## Telegram alerts (optional, free)
1. Message **@BotFather** on Telegram → `/newbot` → copy the token.
2. Message **@userinfobot** → copy your numeric chat id.
3. Set env vars:
```
TELEGRAM_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=987654321
```
Now every new entry and every close pushes to your phone.

## Deploy to Railway (get a URL) — two services

The app is **two services**: a Python **API** (`src/webapp/app.py`) and a Next.js
**dashboard** (`web/`). Deploy both from the same GitHub repo.

**Service 1 — API (Python)**
1. Railway → **New Project → Deploy from GitHub repo** → pick `Perry-Bradley/trading`.
2. It reads `requirements.txt` + `Procfile` and starts the API. Grab its URL under
   **Settings → Domains** (e.g. `https://msnr-api.up.railway.app`).
3. Variables: `TARGET_R=2`, `TF=H4`, `BIAS_TF=D1`, `BROKER=paper`
   (+ `TELEGRAM_*` / `MT5_*` if used). Optional: `LEARNING_RATE`, `ETA0`.

### Live data sources
- **Crypto (BTCUSD)** → **Binance**, real-time, **no key** (uses the public
  `data-api.binance.vision` mirror). Live out of the box.
- **Forex** → **Twelve Data** when `TWELVEDATA_KEY` is set (free key at
  twelvedata.com), otherwise **yfinance (delayed ~15 min)**. To go live on forex:
  set `TWELVEDATA_KEY` on the API service and redeploy. The Data page shows each
  pair's source and whether it's live or delayed.

**Service 2 — dashboard (Next.js)**
4. **New service → same repo**, set **Root Directory = `web`** (Railway auto-detects
   Next.js: `npm install` + `npm run build` + `npm start`).
5. Variable: `NEXT_PUBLIC_API_URL=https://<your-api-url>` (the Service-1 URL).
6. Open the dashboard URL → click **"Refresh data + tick"** to pull data, bootstrap
   the model, generate signals, and start the journal.

> **CORS:** the API allows all origins by default; set `CORS_ORIGIN=https://<dashboard-url>`
> on the API service to lock it to your frontend.

### Keep it learning on a schedule
The platform learns each tick. Automate ticks one of two ways:
- a **Railway cron service**: `curl -X POST "$API_URL/api/tick?refresh=1"`, or
- run the loop on a VPS: `python -m src.runner --interval 3600`.

### Keep it learning on a schedule
The platform learns every time a tick runs. To run ticks automatically, hit the
`/tick` endpoint on a schedule — e.g. a **Railway cron service** running
`curl -X POST https://<your-app>/tick`, or any free uptime pinger.

### Build fix (already in the repo)
If Railway's build fails with *"No GitHub artifact attestations found for
python@3.11.9"*, that's the `mise` installer — `mise.toml` in the repo root
disables that check and fixes it. (Equivalent: set `MISE_PYTHON_GITHUB_ATTESTATIONS=false`
as a service variable.)

### ⚠️ Railway filesystem is ephemeral — REQUIRED for learning to persist
`data/` (journal, paper account, state) and `models/` (the learned model) **reset on
every redeploy** unless you attach a **Railway Volume**. Since the whole point is that
the model *keeps learning*, mount a Volume on the API service at the repo path so
`data/` and `models/` survive. Without it, each redeploy forgets everything it learned.
No database is required — the journal is a CSV and the model is a `.joblib` file; a DB
is only worth it later if you want multi-instance or queryable history.

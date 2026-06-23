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

## Deploy to Railway (get a URL)
1. Push this folder to a GitHub repo.
2. On [railway.app](https://railway.app): **New Project → Deploy from GitHub repo**.
3. Railway reads `requirements.txt` + `Procfile` and starts the web dashboard.
   Your URL appears under the service's **Settings → Domains**.
4. Set env vars (Variables tab): `TARGET_R=2`, `TF=H4`, `BIAS_TF=D1`,
   `BROKER=paper` (+ Telegram/MT5 vars if used).
5. First visit → click **"Run tick + refresh data"** to pull data, bootstrap the
   model, and generate signals.

### Keep it learning on a schedule
The platform learns every time a tick runs. To run ticks automatically, hit the
`/tick` endpoint on a schedule — e.g. a **Railway cron service** running
`curl -X POST https://<your-app>/tick`, or any free uptime pinger.

### ⚠️ Railway filesystem is ephemeral
`data/` (paper account, model, state) resets on redeploy unless you attach a
**Railway Volume** mounted at the project's `data/` path. For durable history,
mount a volume (or later swap state to a small database). Fine to skip while testing.

"""Central configuration for the MSNR trading assistant."""
from pathlib import Path

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Models live UNDER data/ so a single persistent volume (mounted at data/) keeps
# the learned model alongside price data, the paper account and the journal.
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# --- Instruments -------------------------------------------------------------
# Liquid majors + clean liquid crosses (MSNR/SMC respect structure best on liquid
# markets — Module 05: favour majors, avoid thin exotics where slippage blows stops).
# Includes the user's original screenshots' pairs + NZDUSD + BTCUSD.
PAIRS = [
    "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCAD",   # majors
    "EURJPY", "GBPJPY", "CHFJPY",                                 # liquid crosses
    "XAUUSD",                                                     # gold (key SMC instrument)
    "BTCUSD",                                                     # crypto
]

# Crypto behaves differently from forex: 24/7, real volume, no "pip" convention.
CRYPTO = {"BTCUSD"}

# Map our pair names to Yahoo Finance tickers.
YF_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCAD": "USDCAD=X",
    "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "CHFJPY": "CHFJPY=X",
    "XAUUSD": "GC=F",        # gold futures (yfinance); Twelve Data uses XAU/USD spot
    "BTCUSD": "BTC-USD",
}

# --- Timeframes (the MSNR ladder: D1 -> H4 -> H1 -> M30) ----------------------
# value = (yfinance interval, yfinance max period we can request)
TIMEFRAMES = {
    "D1":  {"yf_interval": "1d",  "yf_period": "max"},
    "H4":  {"yf_interval": "1h",  "yf_period": "730d"},  # H4 resampled from H1 below
    "H1":  {"yf_interval": "1h",  "yf_period": "730d"},
    "M30": {"yf_interval": "30m", "yf_period": "60d"},
}

# Point/pip size per instrument:
#   crypto      -> 1.0   (measured in whole dollars, not pips)
#   JPY crosses -> 0.01
#   other FX    -> 0.0001
def pip_size(pair: str) -> float:
    if pair in CRYPTO:
        return 1.0
    if pair == "XAUUSD":
        return 0.1            # gold: 1 pip = 0.1
    return 0.01 if pair.endswith("JPY") else 0.0001

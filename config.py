"""Central configuration for the MSNR trading assistant."""
from pathlib import Path

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# --- Instruments -------------------------------------------------------------
# The forex pairs from the user's practice screenshots, plus BTCUSD (crypto).
PAIRS = ["EURUSD", "GBPUSD", "AUDUSD", "EURNZD", "CHFJPY", "BTCUSD"]

# Crypto behaves differently from forex: 24/7, real volume, no "pip" convention.
CRYPTO = {"BTCUSD"}

# Map our pair names to Yahoo Finance tickers.
YF_TICKERS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X",
    "EURNZD": "EURNZD=X",
    "CHFJPY": "CHFJPY=X",
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
    return 0.01 if pair.endswith("JPY") else 0.0001

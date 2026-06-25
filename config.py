"""Central configuration for the MSNR trading assistant."""
import os
from pathlib import Path

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent


# --- .env loader (zero-dependency) -------------------------------------------
# Loads KEY=value pairs from a local .env so dev doesn't need shell exports.
# On Railway, real env vars take precedence (we never overwrite what's already set).
def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv(ROOT / ".env")
# Railway: mount persistent volume at /data and set DATA_DIR=/data
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Models live UNDER data/ so a single persistent volume (mounted at data/) keeps
# the learned model alongside price data, the paper account and the journal.
MODELS_DIR = DATA_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# --- Instruments -------------------------------------------------------------
# Liquid majors + clean liquid crosses (MSNR/SMC respect structure best on liquid
# markets — Module 05: favour majors, avoid thin exotics where slippage blows stops).
# Includes the user's original screenshots' pairs + NZDUSD + BTCUSD.
PAIRS = [
    # Top 3 most liquid majors (cleanest structure)
    "EURUSD", "GBPUSD", "AUDUSD",
    # Gold (always respected)
    "XAUUSD",
    # Crypto (fast thread - 60s)
    "BTCUSD",
    # Deriv Volatility (fast thread - 60s)
    "V100", "V25",
]

# Crypto behaves differently from forex: 24/7, real volume, no "pip" convention.
CRYPTO = {"BTCUSD"}
INDICES = {"US30", "NAS100", "SPX500", "V100", "V25"}

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
    if pair in CRYPTO or pair in INDICES:
        return 1.0
    if pair == "XAUUSD":
        return 0.1            # gold: 1 pip = 0.1
    return 0.01 if pair.endswith("JPY") else 0.0001

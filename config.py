
"""Central settings for AI QUANT.
Permanently paper-simulation only.
"""

import os


# Application
APP_NAME = "AI QUANT"
APP_VERSION = "4.0.0"
PAPER_MODE = True

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))


# Database
# Configure DB_PATH=/data/ai_quant.db on Render
# when a persistent disk is mounted at /data.
DB_PATH = os.getenv("DB_PATH", "ai_quant.db")


# BingX public market data only
BINGX_BASE_URL = os.getenv(
    "BINGX_BASE_URL",
    "https://open-api.bingx.com"
).rstrip("/")

BINGX_TICKER_PATH = "/openApi/spot/v1/ticker/24hr"
BINGX_KLINE_PATH = "/openApi/spot/v2/market/kline"


# Market configuration
SYMBOLS = tuple(
    s.strip().upper()
    for s in os.getenv(
        "SYMBOLS",
        "BTC-USDT,ETH-USDT,BNB-USDT,SOL-USDT,XRP-USDT"
    ).split(",")
    if s.strip()
)

TIMEFRAMES = ("15m", "1h", "4h")

KLINE_LIMIT = max(
    220,
    min(500, int(os.getenv("KLINE_LIMIT", "300")))
)

SCAN_INTERVAL_SECONDS = max(
    60,
    int(os.getenv("SCAN_INTERVAL_SECONDS", "180"))
)

HTTP_TIMEOUT_SECONDS = max(
    5,
    int(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
)


# Portfolio
STARTING_BALANCE = float(
    os.getenv("STARTING_BALANCE", "200")
)

MAX_OPEN_POSITIONS = max(
    1,
    int(os.getenv("MAX_OPEN_POSITIONS", "3"))
)

# Maximum aggregate open position value / equity
PORTFOLIO_EXPOSURE_LIMIT = 0.10

# Maximum planned loss at stop per new position / equity
PORTFOLIO_RISK_FRACTION = 0.10

FEE_RATE = 0.001
SLIPPAGE_BPS = 5.0

STOP_ATR_MULTIPLIER = 2.0
TARGET_R_MULTIPLIER = 2.0


# Technical analysis
MIN_SCORE_TO_ENTER = 75.0


# Hugging Face AI council
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

HF_API_URL = os.getenv(
    "HF_API_URL",
    "https://router.huggingface.co/v1/chat/completions"
)

HF_MODELS = tuple(
    s.strip()
    for s in os.getenv("HF_MODELS", "").split(",")
    if s.strip()
)

AI_TIMEOUT_SECONDS = max(
    5,
    int(os.getenv("AI_TIMEOUT_SECONDS", "20"))
)

AI_MIN_MODELS = max(
    1,
    int(os.getenv("AI_MIN_MODELS", "2"))
)

AI_MIN_AGREEMENT = min(
    1.0,
    max(
        0.0,
        float(os.getenv("AI_MIN_AGREEMENT", "0.60"))
    )
)


# News engine
NEWS_REFRESH_SECONDS = max(
    120,
    int(os.getenv("NEWS_REFRESH_SECONDS", "600"))
)


# Telegram
TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN", ""
).strip()

TELEGRAM_ADMIN_ID = os.getenv(
    "TELEGRAM_ADMIN_ID", ""
).strip()


# Dashboard
DASHBOARD_REFRESH_SECONDS = 30


# Configuration validation
if STARTING_BALANCE <= 0:
    raise ValueError(
        "STARTING_BALANCE must be positive"
    )

if PORT <= 0 or PORT > 65535:
    raise ValueError("Invalid PORT")

if not SYMBOLS:
    raise ValueError("At least one trading symbol is required")

if not 0 < PORTFOLIO_EXPOSURE_LIMIT <= 1:
    raise ValueError("Invalid portfolio exposure limit")

if not 0 < PORTFOLIO_RISK_FRACTION <= 1:
    raise ValueError("Invalid portfolio risk fraction")

if not 0 <= FEE_RATE < 1:
    raise ValueError("Invalid fee rate")

if SLIPPAGE_BPS < 0:
    raise ValueError("Invalid slippage")

if STOP_ATR_MULTIPLIER <= 0:
    raise ValueError("Invalid stop multiplier")

if TARGET_R_MULTIPLIER <= 0:
    raise ValueError("Invalid target multiplier")

if not 0 <= AI_MIN_AGREEMENT <= 1:
    raise ValueError("Invalid AI agreement threshold")

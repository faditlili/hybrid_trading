
"""Central settings for AI QUANT.
Permanently paper-simulation only.
No real exchange orders are supported.
"""

import os
import math


# --------------------------------------------------
# Environment helpers
# --------------------------------------------------

def env_int(name, default, minimum=None, maximum=None):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        raise ValueError(f"Invalid integer configuration: {name}")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")

    return value


def env_float(name, default, minimum=None, maximum=None):
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        raise ValueError(f"Invalid numeric configuration: {name}")

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")

    return value


# --------------------------------------------------
# Application
# --------------------------------------------------

APP_NAME = "AI QUANT"
APP_VERSION = "4.0.0"

# This application is permanently paper-simulation only.
PAPER_MODE = True

HOST = os.getenv("HOST", "0.0.0.0").strip() or "0.0.0.0"
PORT = env_int("PORT", 7860, 1, 65535)


# --------------------------------------------------
# Database
# --------------------------------------------------

DB_PATH = os.getenv("DB_PATH", "ai_quant.db").strip()

if not DB_PATH:
    raise ValueError("DB_PATH cannot be empty")


# --------------------------------------------------
# BingX public market data
# --------------------------------------------------

BINGX_BASE_URL = os.getenv(
    "BINGX_BASE_URL",
    "https://open-api.bingx.com",
).strip().rstrip("/")

if not BINGX_BASE_URL.startswith(("https://", "http://")):
    raise ValueError("Invalid BINGX_BASE_URL")

BINGX_TICKER_PATH = "/openApi/spot/v1/ticker/24hr"
BINGX_KLINE_PATH = "/openApi/spot/v2/market/kline"


# --------------------------------------------------
# Market configuration
# --------------------------------------------------

SYMBOLS = tuple(
    symbol.strip().upper()
    for symbol in os.getenv(
        "SYMBOLS",
        "BTC-USDT,ETH-USDT,BNB-USDT,SOL-USDT,XRP-USDT",
    ).split(",")
    if symbol.strip()
)

TIMEFRAMES = ("15m", "1h", "4h")

KLINE_LIMIT = env_int(
    "KLINE_LIMIT",
    300,
    220,
    500,
)

SCAN_INTERVAL_SECONDS = env_int(
    "SCAN_INTERVAL_SECONDS",
    180,
    60,
)

HTTP_TIMEOUT_SECONDS = env_int(
    "HTTP_TIMEOUT_SECONDS",
    15,
    5,
)


# --------------------------------------------------
# Portfolio configuration
# --------------------------------------------------

STARTING_BALANCE = env_float(
    "STARTING_BALANCE",
    200.0,
    0.01,
)

MAX_OPEN_POSITIONS = env_int(
    "MAX_OPEN_POSITIONS",
    3,
    1,
)

# Maximum combined market exposure as a fraction
# of current portfolio equity.
PORTFOLIO_EXPOSURE_LIMIT = env_float(
    "PORTFOLIO_EXPOSURE_LIMIT",
    0.10,
    0.000001,
    1.0,
)

# Maximum combined theoretical loss across ALL open
# simulated positions, measured against current equity.
#
# This is an aggregate portfolio limit, NOT a per-trade limit.
# The paper trader must subtract existing open-position risk
# before allowing another position.
PORTFOLIO_RISK_FRACTION = env_float(
    "PORTFOLIO_RISK_FRACTION",
    0.10,
    0.000001,
    1.0,
)

FEE_RATE = env_float(
    "FEE_RATE",
    0.001,
    0.0,
    0.99,
)

SLIPPAGE_BPS = env_float(
    "SLIPPAGE_BPS",
    5.0,
    0.0,
)

STOP_ATR_MULTIPLIER = env_float(
    "STOP_ATR_MULTIPLIER",
    2.0,
    0.000001,
)

TARGET_R_MULTIPLIER = env_float(
    "TARGET_R_MULTIPLIER",
    2.0,
    0.000001,
)


# --------------------------------------------------
# Technical analysis
# --------------------------------------------------

MIN_SCORE_TO_ENTER = env_float(
    "MIN_SCORE_TO_ENTER",
    75.0,
    0.0,
    100.0,
)


# --------------------------------------------------
# Hugging Face AI council
# --------------------------------------------------

HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

HF_API_URL = os.getenv(
    "HF_API_URL",
    "https://router.huggingface.co/v1/chat/completions",
).strip()

if HF_API_URL and not HF_API_URL.startswith(("https://", "http://")):
    raise ValueError("Invalid HF_API_URL")

HF_MODELS = tuple(
    model.strip()
    for model in os.getenv("HF_MODELS", "").split(",")
    if model.strip()
)

AI_TIMEOUT_SECONDS = env_int(
    "AI_TIMEOUT_SECONDS",
    20,
    5,
)

AI_MIN_MODELS = env_int(
    "AI_MIN_MODELS",
    2,
    1,
)

AI_MIN_AGREEMENT = env_float(
    "AI_MIN_AGREEMENT",
    0.60,
    0.0,
    1.0,
)


# --------------------------------------------------
# News engine
# --------------------------------------------------

NEWS_REFRESH_SECONDS = env_int(
    "NEWS_REFRESH_SECONDS",
    600,
    120,
)


# --------------------------------------------------
# Telegram
# --------------------------------------------------

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "",
).strip()

TELEGRAM_ADMIN_ID = os.getenv(
    "TELEGRAM_ADMIN_ID",
    "",
).strip()


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

DASHBOARD_REFRESH_SECONDS = env_int(
    "DASHBOARD_REFRESH_SECONDS",
    30,
    5,
)


# --------------------------------------------------
# Configuration validation
# --------------------------------------------------

if not SYMBOLS:
    raise ValueError("At least one market symbol is required")

if len(set(SYMBOLS)) != len(SYMBOLS):
    raise ValueError("Duplicate market symbols detected")

if not TIMEFRAMES:
    raise ValueError("At least one timeframe is required")

if len(set(TIMEFRAMES)) != len(TIMEFRAMES):
    raise ValueError("Duplicate timeframes detected")

if AI_MIN_MODELS > len(HF_MODELS) and HF_MODELS:
    raise ValueError(
        "AI_MIN_MODELS cannot exceed the number of configured models"
    )

if HF_TOKEN and not HF_MODELS:
    raise ValueError(
        "HF_MODELS must be configured when HF_TOKEN is provided"
    )

if not 0 < PORTFOLIO_EXPOSURE_LIMIT <= 1:
    raise ValueError("Invalid portfolio exposure limit")

if not 0 < PORTFOLIO_RISK_FRACTION <= 1:
    raise ValueError("Invalid aggregate portfolio risk limit")

if not 0 <= FEE_RATE < 1:
    raise ValueError("Invalid fee rate")

if not math.isfinite(SLIPPAGE_BPS):
    raise ValueError("Invalid slippage")

if STOP_ATR_MULTIPLIER <= 0:
    raise ValueError("Invalid stop multiplier")

if TARGET_R_MULTIPLIER <= 0:
    raise ValueError("Invalid target multiplier")

if not 0 <= AI_MIN_AGREEMENT <= 1:
    raise ValueError("Invalid AI agreement threshold")

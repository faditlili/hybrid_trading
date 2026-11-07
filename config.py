
"""Central settings for AI QUANT 4.0.

Permanently paper-simulation only.
Public market data only.
No real exchange orders are supported.
"""

import math
import os
import re

from urllib.parse import urlparse


# --------------------------------------------------
# Environment helpers
# --------------------------------------------------

def env_int(name, default, minimum=None, maximum=None):
    raw = os.getenv(name, str(default)).strip()

    try:
        value = int(raw)
    except (TypeError, ValueError, AttributeError):
        raise ValueError(
            f"Invalid integer configuration: {name}"
        ) from None

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")

    return value


def env_float(name, default, minimum=None, maximum=None):
    raw = os.getenv(name, str(default)).strip()

    try:
        value = float(raw)
    except (TypeError, ValueError, AttributeError):
        raise ValueError(
            f"Invalid numeric configuration: {name}"
        ) from None

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")

    return value


def env_list(name, default=""):
    """Read a comma-separated environment variable."""

    raw = os.getenv(name, default)

    if not isinstance(raw, str):
        raise ValueError(
            f"Invalid list configuration: {name}"
        )

    return tuple(
        item.strip()
        for item in raw.split(",")
        if item.strip()
    )


def validate_https_url(name, value):
    """Validate an external HTTPS service URL."""

    try:
        parsed = urlparse(value)
        hostname = parsed.hostname

        # Accessing port also validates malformed port values.
        _ = parsed.port

    except Exception:
        raise ValueError(
            f"Invalid URL: {name}"
        ) from None

    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            f"{name} must be a valid HTTPS URL "
            "without credentials, query or fragment"
        )


# --------------------------------------------------
# Application
# --------------------------------------------------

APP_NAME = "AI QUANT"
APP_VERSION = "4.0.0"

# This setting is deliberately not configurable.
PAPER_MODE = True

HOST = (
    os.getenv("HOST", "0.0.0.0").strip()
    or "0.0.0.0"
)

PORT = env_int(
    "PORT",
    7860,
    1,
    65535,
)


# --------------------------------------------------
# Database
# --------------------------------------------------

DB_PATH = os.getenv(
    "DB_PATH",
    "ai_quant.db",
).strip()

if not DB_PATH:
    raise ValueError(
        "DB_PATH cannot be empty"
    )


# --------------------------------------------------
# BingX public market data
# --------------------------------------------------

BINGX_BASE_URL = os.getenv(
    "BINGX_BASE_URL",
    "https://open-api.bingx.com",
).strip().rstrip("/")

validate_https_url(
    "BINGX_BASE_URL",
    BINGX_BASE_URL,
)

BINGX_TICKER_PATH = (
    "/openApi/spot/v1/ticker/24hr"
)

BINGX_KLINE_PATH = (
    "/openApi/spot/v2/market/kline"
)


# --------------------------------------------------
# Market configuration
# --------------------------------------------------

SYMBOLS = env_list(
    "SYMBOLS",
    "BTC-USDT,ETH-USDT,BNB-USDT,SOL-USDT,XRP-USDT",
)

TIMEFRAMES = (
    "15m",
    "1h",
    "4h",
)

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
    120,
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
    100,
)

# Maximum combined market exposure.
PORTFOLIO_EXPOSURE_LIMIT = env_float(
    "PORTFOLIO_EXPOSURE_LIMIT",
    0.10,
    0.000001,
    1.0,
)

# Maximum theoretical risk across ALL open positions.
# This is an aggregate portfolio limit, not a per-position limit.
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
    1000.0,
)

STOP_ATR_MULTIPLIER = env_float(
    "STOP_ATR_MULTIPLIER",
    2.0,
    0.000001,
    100.0,
)

TARGET_R_MULTIPLIER = env_float(
    "TARGET_R_MULTIPLIER",
    2.0,
    0.000001,
    100.0,
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

HF_TOKEN = os.getenv(
    "HF_TOKEN",
    "",
).strip()

HF_API_URL = os.getenv(
    "HF_API_URL",
    "https://router.huggingface.co/v1/chat/completions",
).strip()

validate_https_url(
    "HF_API_URL",
    HF_API_URL,
)

HF_MODELS = env_list(
    "HF_MODELS",
    "",
)

AI_TIMEOUT_SECONDS = env_int(
    "AI_TIMEOUT_SECONDS",
    20,
    5,
    180,
)

AI_MIN_MODELS = env_int(
    "AI_MIN_MODELS",
    2,
    1,
    20,
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

# Symbols must be unique and use BASE-USDT format.
if not SYMBOLS:
    raise ValueError(
        "At least one market symbol is required"
    )

if len(set(SYMBOLS)) != len(SYMBOLS):
    raise ValueError(
        "Duplicate market symbols detected"
    )

for symbol in SYMBOLS:

    if not re.fullmatch(
        r"[A-Z0-9]+-USDT",
        symbol
    ):
        raise ValueError(
            f"Invalid market symbol: {symbol}. "
            "Expected BASE-USDT format."
        )


# Validate the supported analysis timeframes.
SUPPORTED_TIMEFRAMES = {
    "15m",
    "1h",
    "4h",
}

if not TIMEFRAMES:
    raise ValueError(
        "At least one timeframe is required"
    )

if len(set(TIMEFRAMES)) != len(TIMEFRAMES):
    raise ValueError(
        "Duplicate timeframes detected"
    )

if not set(TIMEFRAMES).issubset(
    SUPPORTED_TIMEFRAMES
):
    raise ValueError(
        "Unsupported timeframe configured"
    )

if not {
    "15m",
    "1h",
    "4h",
}.issubset(set(TIMEFRAMES)):
    raise ValueError(
        "15m, 1h and 4h are required"
    )


# AI council validation.
if HF_TOKEN and not HF_MODELS:
    raise ValueError(
        "HF_MODELS must be configured when HF_TOKEN is provided"
    )

if HF_TOKEN and AI_MIN_MODELS > len(HF_MODELS):
    raise ValueError(
        "AI_MIN_MODELS cannot exceed configured model count"
    )

if len(set(HF_MODELS)) != len(HF_MODELS):
    raise ValueError(
        "Duplicate AI models detected"
    )


# Portfolio validation.
if not 0 < PORTFOLIO_EXPOSURE_LIMIT <= 1:
    raise ValueError(
        "Invalid portfolio exposure limit"
    )

if not 0 < PORTFOLIO_RISK_FRACTION <= 1:
    raise ValueError(
        "Invalid aggregate portfolio risk limit"
    )

if not 0 <= FEE_RATE < 1:
    raise ValueError(
        "Invalid fee rate"
    )

if not 0 <= SLIPPAGE_BPS <= 1000:
    raise ValueError(
        "Invalid slippage"
    )

if STOP_ATR_MULTIPLIER <= 0:
    raise ValueError(
        "Invalid stop multiplier"
    )

if TARGET_R_MULTIPLIER <= 0:
    raise ValueError(
        "Invalid target multiplier"
    )


# AI validation.
if not 0 <= AI_MIN_AGREEMENT <= 1:
    raise ValueError(
        "Invalid AI agreement threshold"
    )


# Telegram validation.
if bool(TELEGRAM_TOKEN) != bool(TELEGRAM_ADMIN_ID):
    raise ValueError(
        "TELEGRAM_TOKEN and TELEGRAM_ADMIN_ID "
        "must be configured together"
    )

if (
    TELEGRAM_ADMIN_ID
    and not TELEGRAM_ADMIN_ID.isdigit()
):
    raise ValueError(
        "TELEGRAM_ADMIN_ID must contain digits only"
    )

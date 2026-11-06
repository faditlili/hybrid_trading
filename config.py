
import math
import os
from pathlib import Path


# ============================================================
# APPLICATION
# ============================================================

APP_NAME = "AI QUANT"
APP_VERSION = "3.1.0"

# This project is permanently restricted to paper trading.
# No real order execution is implemented or authorized here.
PAPER_MODE = True


# ============================================================
# SERVER
# ============================================================

HOST = os.getenv("HOST", "0.0.0.0")

try:
    PORT = int(os.getenv("PORT", "7860"))
except ValueError:
    PORT = 7860


# ============================================================
# DATABASE
# ============================================================

DB_PATH = os.getenv("DB_PATH", "ai_quant.db")


# ============================================================
# MARKET DATA
# ============================================================

BINANCE_BASE_URL = os.getenv(
    "BINANCE_BASE_URL",
    "https://api.binance.com"
).rstrip("/")

TIMEFRAME = os.getenv("TIMEFRAME", "15m")

KLINE_LIMIT = 200

MIN_QUOTE_VOLUME = 5_000_000.0

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "XRPUSDT",
]


# ============================================================
# ENGINE
# ============================================================

SCAN_INTERVAL_SECONDS = 180

MAX_SCAN_DURATION_SECONDS = 150

MAX_OPEN_POSITIONS = 3

MIN_SCORE_TO_ENTER = 72


# ============================================================
# PAPER ACCOUNT
# ============================================================

INITIAL_BALANCE = 200.0

RISK_PER_TRADE_PCT = 0.005

MAX_ALLOCATION_PCT = 0.10

FEE_RATE = 0.001

SIMULATED_SLIPPAGE_BPS = 5.0

STOP_ATR_MULTIPLIER = 2.0

TARGET_R_MULTIPLIER = 2.0


# ============================================================
# AI COUNCIL
# ============================================================

HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

HF_API_URL = os.getenv(
    "HF_API_URL",
    "https://router.huggingface.co/v1/chat/completions"
).strip()

HF_MODELS = [
    model.strip()
    for model in os.getenv("HF_MODELS", "").split(",")
    if model.strip()
]

AI_REQUEST_TIMEOUT_SECONDS = 30

AI_MAX_CONCURRENT_REQUESTS = 3

AI_MIN_VALID_MODELS = 2

AI_MIN_AGREEMENT_RATIO = 0.60


# ============================================================
# NEWS ENGINE
# ============================================================

NEWS_REFRESH_SECONDS = 300

NEWS_MAX_ITEMS = 60

NEWS_REQUEST_TIMEOUT_SECONDS = 15


# ============================================================
# TELEGRAM
# ============================================================

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    ""
).strip()

_telegram_admin = os.getenv(
    "TELEGRAM_ADMIN_ID",
    ""
).strip()

try:
    TELEGRAM_ADMIN_ID = (
        int(_telegram_admin)
        if _telegram_admin
        else None
    )
except ValueError:
    TELEGRAM_ADMIN_ID = None


# ============================================================
# HTTP SETTINGS
# ============================================================

HTTP_TIMEOUT_SECONDS = 15

HTTP_CONNECT_TIMEOUT_SECONDS = 8

HTTP_MAX_CONNECTIONS = 10

HTTP_RETRY_ATTEMPTS = 2


# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = os.getenv(
    "LOG_LEVEL",
    "INFO"
).upper()


# ============================================================
# CONFIGURATION VALIDATION
# ============================================================

def _is_finite_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def validate_config():
    """
    Validate application configuration before startup.

    Raises:
        ValueError: If an invalid configuration is detected.
    """

    errors = []

    if not PAPER_MODE:
        errors.append(
            "PAPER_MODE must remain True."
        )

    if not isinstance(PORT, int) or not 1 <= PORT <= 65535:
        errors.append("PORT must be between 1 and 65535.")

    if not isinstance(SCAN_INTERVAL_SECONDS, int):
        errors.append("SCAN_INTERVAL_SECONDS must be an integer.")
    elif SCAN_INTERVAL_SECONDS <= 0:
        errors.append("SCAN_INTERVAL_SECONDS must be positive.")

    if not isinstance(MAX_SCAN_DURATION_SECONDS, int):
        errors.append("MAX_SCAN_DURATION_SECONDS must be an integer.")
    elif MAX_SCAN_DURATION_SECONDS <= 0:
        errors.append("MAX_SCAN_DURATION_SECONDS must be positive.")

    if not isinstance(MAX_OPEN_POSITIONS, int):
        errors.append("MAX_OPEN_POSITIONS must be an integer.")
    elif MAX_OPEN_POSITIONS < 1:
        errors.append("MAX_OPEN_POSITIONS must be at least 1.")

    if not isinstance(MIN_SCORE_TO_ENTER, int):
        errors.append("MIN_SCORE_TO_ENTER must be an integer.")
    elif not 0 <= MIN_SCORE_TO_ENTER <= 100:
        errors.append("MIN_SCORE_TO_ENTER must be between 0 and 100.")

    if not _is_finite_number(INITIAL_BALANCE):
        errors.append("INITIAL_BALANCE must be finite.")
    elif INITIAL_BALANCE <= 0:
        errors.append("INITIAL_BALANCE must be positive.")

    if not _is_finite_number(RISK_PER_TRADE_PCT):
        errors.append("RISK_PER_TRADE_PCT must be finite.")
    elif not 0 < RISK_PER_TRADE_PCT <= 0.01:
        errors.append(
            "RISK_PER_TRADE_PCT must be greater than 0 and at most 0.01."
        )

    if not _is_finite_number(MAX_ALLOCATION_PCT):
        errors.append("MAX_ALLOCATION_PCT must be finite.")
    elif not 0 < MAX_ALLOCATION_PCT <= 1:
        errors.append(
            "MAX_ALLOCATION_PCT must be greater than 0 and at most 1."
        )

    if not _is_finite_number(FEE_RATE):
        errors.append("FEE_RATE must be finite.")
    elif not 0 <= FEE_RATE < 1:
        errors.append("FEE_RATE must be between 0 and 1.")

    if not _is_finite_number(SIMULATED_SLIPPAGE_BPS):
        errors.append("SIMULATED_SLIPPAGE_BPS must be finite.")
    elif not 0 <= SIMULATED_SLIPPAGE_BPS < 10000:
        errors.append(
            "SIMULATED_SLIPPAGE_BPS must be between 0 and 10000."
        )

    if not _is_finite_number(STOP_ATR_MULTIPLIER):
        errors.append("STOP_ATR_MULTIPLIER must be finite.")
    elif STOP_ATR_MULTIPLIER <= 0:
        errors.append("STOP_ATR_MULTIPLIER must be positive.")

    if not _is_finite_number(TARGET_R_MULTIPLIER):
        errors.append("TARGET_R_MULTIPLIER must be finite.")
    elif TARGET_R_MULTIPLIER <= 0:
        errors.append("TARGET_R_MULTIPLIER must be positive.")

    if not isinstance(KLINE_LIMIT, int):
        errors.append("KLINE_LIMIT must be an integer.")
    elif KLINE_LIMIT < 60 or KLINE_LIMIT > 1000:
        errors.append("KLINE_LIMIT must be between 60 and 1000.")

    if not _is_finite_number(MIN_QUOTE_VOLUME):
        errors.append("MIN_QUOTE_VOLUME must be finite.")
    elif MIN_QUOTE_VOLUME < 0:
        errors.append("MIN_QUOTE_VOLUME cannot be negative.")

    if not SYMBOLS:
        errors.append("SYMBOLS cannot be empty.")

    if len(SYMBOLS) != len(set(SYMBOLS)):
        errors.append("SYMBOLS contains duplicate entries.")

    for symbol in SYMBOLS:
        if (
            not isinstance(symbol, str)
            or not symbol
            or symbol != symbol.upper()
        ):
            errors.append(
                f"Invalid trading symbol: {symbol!r}"
            )

    if not BINANCE_BASE_URL.startswith("https://"):
        errors.append("BINANCE_BASE_URL must use HTTPS.")

    if not DB_PATH:
        errors.append("DB_PATH cannot be empty.")

    if AI_MIN_VALID_MODELS < 1:
        errors.append("AI_MIN_VALID_MODELS must be at least 1.")

    if not _is_finite_number(AI_MIN_AGREEMENT_RATIO):
        errors.append("AI_MIN_AGREEMENT_RATIO must be finite.")
    elif not 0.5 < AI_MIN_AGREEMENT_RATIO <= 1:
        errors.append(
            "AI_MIN_AGREEMENT_RATIO must be greater than 0.5 and at most 1."
        )

    if AI_MAX_CONCURRENT_REQUESTS < 1:
        errors.append(
            "AI_MAX_CONCURRENT_REQUESTS must be at least 1."
        )

    if errors:
        raise ValueError(
            "Invalid application configuration:\n- "
            + "\n- ".join(errors)
        )

    return True


# ============================================================
# STARTUP VALIDATION
# ============================================================

validate_config()

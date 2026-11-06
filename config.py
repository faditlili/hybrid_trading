import os
import math


APP_NAME = "AI QUANT"
APP_VERSION = "3.0.0"

# Paper trading only
PAPER_MODE = True

# Account
INITIAL_BALANCE = 200.0

# Trading
SCAN_INTERVAL_SECONDS = 180
MAX_OPEN_POSITIONS = 3
MIN_SCORE_TO_ENTER = 72

RISK_PER_TRADE_PCT = 0.005
MAX_ALLOCATION_PCT = 0.10

FEE_RATE = 0.001
SIMULATED_SLIPPAGE_BPS = 3

STOP_ATR_MULTIPLIER = 1.8
TARGET_R_MULTIPLIER = 2.0

# Market data
BINANCE_BASE_URL = "https://api.binance.com"

TIMEFRAME = "15m"
KLINE_LIMIT = 100

MIN_QUOTE_VOLUME = 5_000_000

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "AVAXUSDT",
    "DOGEUSDT",
    "LINKUSDT",
    "NEARUSDT",
    "PEPEUSDT",
]

# Database
DB_PATH = os.getenv(
    "DB_PATH",
    "ai_quant.sqlite3"
)

# Hugging Face
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

HF_API_URL = (
    "https://router.huggingface.co/v1/chat/completions"
)

HF_TIMEOUT = 35

HF_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
    "meta-llama/Llama-3.1-8B-Instruct",
]

# Telegram
TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    ""
).strip()

ALLOWED_ADMIN_ID = os.getenv(
    "ALLOWED_ADMIN_ID",
    ""
).strip()

# Server
HOST = "0.0.0.0"
DEFAULT_PORT = 7860


def get_float(name, default, minimum=None, maximum=None):

    try:
        value = float(os.getenv(name, default))

        if not math.isfinite(value):
            raise ValueError("Non-finite value")

    except (TypeError, ValueError, OverflowError):
        value = float(default)

    if minimum is not None:
        value = max(minimum, value)

    if maximum is not None:
        value = min(maximum, value)

    return value


def get_int(name, default, minimum=None, maximum=None):

    try:
        raw = os.getenv(name)

        if raw is None:
            value = int(default)
        else:
            value = int(raw)

    except (TypeError, ValueError, OverflowError):
        value = int(default)

    if minimum is not None:
        value = max(minimum, value)

    if maximum is not None:
        value = min(maximum, value)

    return value


# Environment overrides

INITIAL_BALANCE = get_float(
    "INITIAL_BALANCE",
    INITIAL_BALANCE,
    1,
    1_000_000
)

SCAN_INTERVAL_SECONDS = get_int(
    "SCAN_INTERVAL_SECONDS",
    SCAN_INTERVAL_SECONDS,
    10,
    3600
)

MAX_OPEN_POSITIONS = get_int(
    "MAX_OPEN_POSITIONS",
    MAX_OPEN_POSITIONS,
    1,
    20
)

MIN_SCORE_TO_ENTER = get_int(
    "MIN_SCORE_TO_ENTER",
    MIN_SCORE_TO_ENTER,
    1,
    100
)

RISK_PER_TRADE_PCT = get_float(
    "RISK_PER_TRADE_PCT",
    RISK_PER_TRADE_PCT,
    0.0001,
    0.05
)

MAX_ALLOCATION_PCT = get_float(
    "MAX_ALLOCATION_PCT",
    MAX_ALLOCATION_PCT,
    0.001,
    0.50
)

FEE_RATE = get_float(
    "FEE_RATE",
    FEE_RATE,
    0,
    0.02
)

SIMULATED_SLIPPAGE_BPS = get_float(
    "SIMULATED_SLIPPAGE_BPS",
    SIMULATED_SLIPPAGE_BPS,
    0,
    100
)

STOP_ATR_MULTIPLIER = get_float(
    "STOP_ATR_MULTIPLIER",
    STOP_ATR_MULTIPLIER,
    0.1,
    10
)

TARGET_R_MULTIPLIER = get_float(
    "TARGET_R_MULTIPLIER",
    TARGET_R_MULTIPLIER,
    0.1,
    20
)

MIN_QUOTE_VOLUME = get_float(
    "MIN_QUOTE_VOLUME",
    MIN_QUOTE_VOLUME,
    0
)

HF_TIMEOUT = get_int(
    "HF_TIMEOUT",
    HF_TIMEOUT,
    5,
    120
)

# Validate symbols
SYMBOLS = list(dict.fromkeys(
    symbol.strip().upper()
    for symbol in SYMBOLS
    if isinstance(symbol, str) and symbol.strip()
))

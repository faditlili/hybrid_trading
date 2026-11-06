import os
import math


# ==========================================
# AI QUANT - CORE CONFIGURATION
# ==========================================

APP_NAME = "AI QUANT"

PAPER_MODE = True


# ==========================================
# ENVIRONMENT HELPERS
# ==========================================

def get_float(name, default, minimum=None, maximum=None):
    value = float(os.getenv(name, str(default)))

    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} is below minimum")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} is above maximum")

    return value


def get_int(name, default, minimum=None, maximum=None):
    value = int(os.getenv(name, str(default)))

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} is below minimum")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} is above maximum")

    return value


# ==========================================
# VIRTUAL ACCOUNT
# ==========================================

INITIAL_BALANCE = get_float(
    "INITIAL_BALANCE", 200, 0.01
)


# ==========================================
# ENGINE SETTINGS
# ==========================================

SCAN_INTERVAL_SECONDS = get_int(
    "SCAN_INTERVAL_SECONDS", 180, 10
)

MAX_OPEN_POSITIONS = get_int(
    "MAX_OPEN_POSITIONS", 3, 1
)

MIN_SCORE_TO_ENTER = get_int(
    "MIN_SCORE_TO_ENTER", 72, 0, 100
)


# ==========================================
# SIMULATION RISK SETTINGS
# ==========================================

MAX_ALLOCATION_PCT = get_float(
    "MAX_ALLOCATION_PCT", 0.10, 0.001, 1
)

RISK_PER_TRADE_PCT = get_float(
    "RISK_PER_TRADE_PCT", 0.005, 0.001, 1
)

FEE_RATE = get_float(
    "PAPER_FEE_RATE", 0.001, 0, 0.1
)

SIMULATED_SLIPPAGE_BPS = get_float(
    "SIMULATED_SLIPPAGE_BPS", 3, 0, 5000
)

STOP_ATR_MULTIPLIER = get_float(
    "STOP_ATR_MULTIPLIER", 1.8, 0.01
)

TARGET_R_MULTIPLIER = get_float(
    "TARGET_R_MULTIPLIER", 2.0, 0.01
)


# ==========================================
# MARKET DATA
# ==========================================

MIN_QUOTE_VOLUME = get_float(
    "MIN_QUOTE_VOLUME", 5000000, 0
)

DEFAULT_SYMBOLS = (
    "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,"
    "ADAUSDT,AVAXUSDT,DOGEUSDT,LINKUSDT,"
    "NEARUSDT,PEPEUSDT"
)

SYMBOLS = list(dict.fromkeys(
    symbol.strip().upper()
    for symbol in os.getenv(
        "SYMBOLS",
        DEFAULT_SYMBOLS
    ).split(",")
    if symbol.strip()
))

if not SYMBOLS:
    raise ValueError("SYMBOLS cannot be empty")


TIMEFRAME = os.getenv(
    "TIMEFRAME", "15m"
)

KLINE_LIMIT = get_int(
    "KLINE_LIMIT", 100, 61, 1000
)


# ==========================================
# DATABASE
# ==========================================

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "ai_quant.sqlite3"
)


# ==========================================
# PUBLIC MARKET DATA API
# ==========================================

BINANCE_BASE_URL = os.getenv(
    "BINANCE_BASE_URL",
    "https://api.binance.com"
).rstrip("/")


# ==========================================
# HUGGING FACE AI COUNCIL
# ==========================================

HF_TOKEN = os.getenv(
    "HF_TOKEN", ""
)

HF_CHAT_COMPLETIONS_URL = os.getenv(
    "HF_CHAT_COMPLETIONS_URL",
    "https://router.huggingface.co/v1/chat/completions"
)

HF_AI_TIMEOUT = get_int(
    "HF_AI_TIMEOUT", 35, 5, 120
)

HF_QWEN_MODEL = os.getenv(
    "HF_QWEN_MODEL",
    "Qwen/Qwen2.5-7B-Instruct"
)

HF_DEEPSEEK_MODEL = os.getenv(
    "HF_DEEPSEEK_MODEL",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
)

HF_LLAMA_MODEL = os.getenv(
    "HF_LLAMA_MODEL",
    "meta-llama/Llama-3.1-8B-Instruct"
)


# ==========================================
# TELEGRAM
# ==========================================

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN", ""
)

ALLOWED_ADMIN_ID = os.getenv(
    "ALLOWED_ADMIN_ID", ""
)

import os

APP_NAME = "AI QUANT"

INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "200"))
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "180"))

MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
MIN_SCORE_TO_ENTER = int(os.getenv("MIN_SCORE_TO_ENTER", "72"))

MAX_ALLOCATION_PCT = float(os.getenv("MAX_ALLOCATION_PCT", "0.10"))
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.005"))

FEE_RATE = float(os.getenv("PAPER_FEE_RATE", "0.001"))
SIMULATED_SLIPPAGE_BPS = float(os.getenv("SIMULATED_SLIPPAGE_BPS", "3"))

STOP_ATR_MULTIPLIER = float(os.getenv("STOP_ATR_MULTIPLIER", "1.8"))
TARGET_R_MULTIPLIER = float(os.getenv("TARGET_R_MULTIPLIER", "2.0"))

MIN_QUOTE_VOLUME = float(os.getenv("MIN_QUOTE_VOLUME", "5000000"))

SYMBOLS = [
    s.strip().upper()
    for s in os.getenv(
        "SYMBOLS",
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,ADAUSDT,AVAXUSDT,DOGEUSDT,LINKUSDT,NEARUSDT,PEPEUSDT"
    ).split(",")
    if s.strip()
]

TIMEFRAME = os.getenv("TIMEFRAME", "15m")
KLINE_LIMIT = int(os.getenv("KLINE_LIMIT", "100"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "ai_quant.sqlite3")

BINANCE_BASE_URL = os.getenv(
    "BINANCE_BASE_URL",
    "https://api.binance.com"
)

HF_TOKEN = os.getenv("HF_TOKEN", "")

HF_API_URL = os.getenv(
    "HF_API_URL",
    "https://router.huggingface.co/hf-inference/models"
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ALLOWED_ADMIN_ID = os.getenv("ALLOWED_ADMIN_ID", "")

"""Central application settings."""
import os

APP_NAME = "AI QUANT"
APP_VERSION = "4.0.0"
PAPER_MODE = True
BINGX_BASE_URL = (
    "https://bingx.com"
)
BINGX_KLINE_PATH = (
    "/openApi/spot/v2/market/kline"
)
BINGX_TICKER_PATH = (
    "/openApi/spot/v1/ticker/24hr"
)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))
DB_PATH = os.getenv(
    "DB_PATH", "ai_quant.db"
)
_DEFS = (
    "BTC-USDT,ETH-USDT,BNB-USDT,"
    "SOL-USDT,XRP-USDT"
)

SYMBOLS = tuple(
    s.strip().upper()
    for s in os.getenv(
        "SYMBOLS", _DEFS
    ).split(",")
    if s.strip()
)
TIMEFRAME = os.getenv("TIMEFRAME", "15m")
KLINE_LIMIT = int(
    os.getenv("KLINE_LIMIT", "300")
)
SCAN_INTERVAL_SECONDS = int(
    os.getenv("SCAN_INTERVAL_SECONDS", "180")
)
MIN_SCORE_TO_ENTER = float(
    os.getenv("MIN_SCORE_TO_ENTER", "72")
)
MAX_OPEN_POSITIONS = int(
    os.getenv("MAX_OPEN_POSITIONS", "3")
)
STARTING_BALANCE = float(
    os.getenv("STARTING_BALANCE", "200")
)
RISK_PER_TRADE = float(
    os.getenv("RISK_PER_TRADE", "0.10")
)
MAX_ALLOCATION = float(
    os.getenv("MAX_ALLOCATION", "0.50")
)
FEE_RATE = float(
    os.getenv("PAPER_FEE_RATE", "0.001")
)
SLIPPAGE_BPS = float(
    os.getenv("PAPER_SLIPPAGE_BPS", "5")
)
DASHBOARD_USERNAME = os.getenv(
    "DASHBOARD_USERNAME", ""
)
DASHBOARD_PASSWORD = os.getenv(
    "DASHBOARD_PASSWORD", ""
)
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_API_URL = (
    "https://huggingface.co"
    "/v1/chat/completions"
)

_MODELS = (
    "meta-llama/Llama-3-8b-instruct,"
    "mistralai/Mixtral-8x7B-Instruct-v0.1"
)
HF_MODELS = tuple(
    x.strip()
    for x in os.getenv(
        "HF_MODELS", _MODELS
    ).split(",")
    if x.strip()
)
AI_TIMEOUT_SECONDS = float(
    os.getenv("AI_TIMEOUT_SECONDS", "25")
)
AI_MIN_MODELS = int(
    os.getenv("AI_MIN_MODELS", "2")
)
AI_MIN_AGREEMENT = float(
    os.getenv("AI_MIN_AGREEMENT", "0.60")
)
NEWS_REFRESH_SECONDS = int(
    os.getenv("NEWS_REFRESH_SECONDS", "300")
)
TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN", ""
)
TELEGRAM_ADMIN_ID = os.getenv(
    "TELEGRAM_ADMIN_ID", ""
)
HTTP_TIMEOUT_SECONDS = float(
    os.getenv("HTTP_TIMEOUT_SECONDS", "15")
)

if not PAPER_MODE:
    raise RuntimeError(
        "Safety rule violation: "
        "Real trading is locked."
    )
if not 60 <= KLINE_LIMIT <= 1440:
    raise ValueError(
        "KLINE_LIMIT limits violated."
    )

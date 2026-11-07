"""Central settings. This application is permanently paper-simulation only."""
import os
from pathlib import Path

APP_NAME = "AI QUANT"
APP_VERSION = "4.0.0"
PAPER_MODE = True
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))
DB_PATH = os.getenv("DB_PATH", "/data/ai_quant.db" if Path("/data").exists() else "ai_quant.db")
BINGX_BASE_URL = os.getenv("BINGX_BASE_URL", "https://open-api.bingx.com").rstrip("/")
BINGX_TICKER_PATH = "/openApi/spot/v1/ticker/24hr"
BINGX_KLINE_PATH = "/openApi/spot/v2/market/kline"
SYMBOLS = tuple(s.strip().upper() for s in os.getenv("SYMBOLS", "BTC-USDT,ETH-USDT,BNB-USDT,SOL-USDT,XRP-USDT").split(",") if s.strip())
TIMEFRAMES = ("15m", "1h", "4h")
KLINE_LIMIT = max(220, min(500, int(os.getenv("KLINE_LIMIT", "300"))))
SCAN_INTERVAL_SECONDS = max(60, int(os.getenv("SCAN_INTERVAL_SECONDS", "180")))
HTTP_TIMEOUT_SECONDS = max(5, int(os.getenv("HTTP_TIMEOUT_SECONDS", "15")))
STARTING_BALANCE = float(os.getenv("STARTING_BALANCE", "200"))
MAX_OPEN_POSITIONS = max(1, int(os.getenv("MAX_OPEN_POSITIONS", "3")))
PORTFOLIO_EXPOSURE_LIMIT = 0.10  # aggregate open notional / current equity
FEE_RATE = 0.001
SLIPPAGE_BPS = 5.0
STOP_ATR_MULTIPLIER = 2.0
TARGET_R_MULTIPLIER = 2.0
MIN_SCORE_TO_ENTER = 75.0
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
HF_API_URL = os.getenv("HF_API_URL", "https://router.huggingface.co/v1/chat/completions")
HF_MODELS = tuple(s.strip() for s in os.getenv("HF_MODELS", "").split(",") if s.strip())
AI_TIMEOUT_SECONDS = max(5, int(os.getenv("AI_TIMEOUT_SECONDS", "20")))
AI_MIN_MODELS = max(1, int(os.getenv("AI_MIN_MODELS", "2")))
AI_MIN_AGREEMENT = min(1.0, max(0.0, float(os.getenv("AI_MIN_AGREEMENT", "0.60"))))
NEWS_REFRESH_SECONDS = max(120, int(os.getenv("NEWS_REFRESH_SECONDS", "600")))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "").strip()
DASHBOARD_REFRESH_SECONDS = 30

if STARTING_BALANCE <= 0:
    raise ValueError("STARTING_BALANCE must be positive")
if not 0 < PORTFOLIO_EXPOSURE_LIMIT <= 1:
    raise ValueError("Invalid portfolio exposure limit")

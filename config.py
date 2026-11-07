
# MARKET DATA - BINGX
# ============================================================

BINGX_BASE_URL = os.getenv(
    "BINGX_BASE_URL",
    "https://open-api.bingx.com",
).strip().rstrip("/")

# ============================================================
# BINGX API CREDENTIALS
# ============================================================

BINGX_API_KEY = os.getenv(
    "BINGX_API_KEY", ""
).strip()

BINGX_SECRET_KEY = os.getenv(
    "BINGX_SECRET_KEY", ""
).strip()

TIMEFRAME = os.getenv("TIMEFRAME", "15m").strip()

KLINE_LIMIT = 200

MIN_QUOTE_VOLUME = 5_000_000.0

# ============================================================
# MARKET SYMBOLS - BINGX
# ============================================================

SYMBOLS = [
    "BTC-USDT",
    "ETH-USDT",
    "BNB-USDT",
    "SOL-USDT",
    "XRP-USDT",
]

BINGX_SYMBOL_MAP = {
    "BTC-USDT": "BTC-USDT",
    "ETH-USDT": "ETH-USDT",
    "BNB-USDT": "BNB-USDT",
    "SOL-USDT": "SOL-USDT",
    "XRP-USDT": "XRP-USDT",
}
    
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
    "https://router.huggingface.co/v1/chat/completions",
).strip()

HF_MODELS = [
    model.strip()
    for model in os.getenv("HF_MODELS", "").split(",")
    if model.strip()
]

AI_REQUEST_TIMEOUT_SECONDS = 30

# Compatibility alias for older code.
HF_TIMEOUT = AI_REQUEST_TIMEOUT_SECONDS

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
    "",
).strip()

_telegram_admin = os.getenv(
    "TELEGRAM_ADMIN_ID",
    "",
).strip()

try:
    TELEGRAM_ADMIN_ID = (
        int(_telegram_admin)
        if _telegram_admin
        else None
    )
except (TypeError, ValueError, OverflowError):
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

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper()


# ============================================================
# VALIDATION HELPERS
# ============================================================

def _is_finite_number(value):
    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _valid_https_url(value):
    try:
        parsed = urlparse(value)

        return (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except (TypeError, ValueError):
        return False


# ============================================================
# CONFIGURATION VALIDATION
# ============================================================


def validate_config():
    errors = []

    # SAFETY
    if PAPER_MODE is not True:
        errors.append("PAPER_MODE must remain True.")

    # SERVER
    if not isinstance(HOST, str) or not HOST:
        errors.append("HOST must be a non-empty string.")

    if (
        isinstance(PORT, bool)
        or not isinstance(PORT, int)
        or not 1 <= PORT <= 65535
    ):
        errors.append("PORT must be between 1 and 65535.")

    # DATABASE
    if not isinstance(DB_PATH, str) or not DB_PATH:
        errors.append("DB_PATH must be a non-empty string.")

    # MARKET DATA
    if not _valid_https_url(BINGX_BASE_URL):
        errors.append("BINGX_BASE_URL must be a valid HTTPS URL.")

    if not isinstance(TIMEFRAME, str) or not TIMEFRAME:
        errors.append("TIMEFRAME must be a non-empty string.")

    if (
        isinstance(KLINE_LIMIT, bool)
        or not isinstance(KLINE_LIMIT, int)
        or not 60 <= KLINE_LIMIT <= 1000
    ):
        errors.append("KLINE_LIMIT must be between 60 and 1000.")

    if not _is_finite_number(MIN_QUOTE_VOLUME):
        errors.append("MIN_QUOTE_VOLUME must be finite.")
    elif MIN_QUOTE_VOLUME < 0:
        errors.append("MIN_QUOTE_VOLUME cannot be negative.")

    # SYMBOLS
    if not isinstance(SYMBOLS, list) or not SYMBOLS:
        errors.append("SYMBOLS must be a non-empty list.")
    else:
        if not all(isinstance(s, str) for s in SYMBOLS):
            errors.append("All SYMBOLS entries must be strings.")
        else:
            if len(SYMBOLS) != len(set(SYMBOLS)):
                errors.append("SYMBOLS contains duplicate entries.")

            for symbol in SYMBOLS:
                if (
                    not symbol
                    or symbol != symbol.upper()
                    or symbol.count("-") != 1
                    or not all(
                        part.isalnum()
                        for part in symbol.split("-")
                    )
                ):
                    errors.append(
                        f"Invalid trading symbol: {symbol!r}"
                    )
                    
    # BINGX SYMBOL MAP
    if not isinstance(BINGX_SYMBOL_MAP,dict): 
        errors.append("BINGX_SYMBOL_MAP must be a dictionary.")
    elif isinstance(SYMBOLS, list):
        for symbol in SYMBOLS:
            if symbol not in BINGX_SYMBOL_MAP:
                errors.append(
                    f"Missing BingX mapping for {symbol}."
                )
            elif (
                not isinstance(BINGX_SYMBOL_MAP[symbol], str)
                or not BINGX_SYMBOL_MAP[symbol].strip()
            ):
                errors.append(
                    f"Invalid BingX mapping for {symbol}."
                )

    # ENGINE
    integer_settings = {
        "SCAN_INTERVAL_SECONDS": SCAN_INTERVAL_SECONDS,
        "MAX_SCAN_DURATION_SECONDS": MAX_SCAN_DURATION_SECONDS,
        "MAX_OPEN_POSITIONS": MAX_OPEN_POSITIONS,
        "MIN_SCORE_TO_ENTER": MIN_SCORE_TO_ENTER,
    }

    for name, value in integer_settings.items():
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{name} must be an integer.")

    if isinstance(SCAN_INTERVAL_SECONDS, int) and not isinstance(SCAN_INTERVAL_SECONDS, bool):
        if SCAN_INTERVAL_SECONDS <= 0:
            errors.append("SCAN_INTERVAL_SECONDS must be positive.")

    if isinstance(MAX_SCAN_DURATION_SECONDS, int) and not isinstance(MAX_SCAN_DURATION_SECONDS, bool):
        if MAX_SCAN_DURATION_SECONDS <= 0:
            errors.append("MAX_SCAN_DURATION_SECONDS must be positive.")

    if isinstance(MAX_OPEN_POSITIONS, int) and not isinstance(MAX_OPEN_POSITIONS, bool):
        if MAX_OPEN_POSITIONS < 1:
            errors.append("MAX_OPEN_POSITIONS must be at least 1.")

    if isinstance(MIN_SCORE_TO_ENTER, int) and not isinstance(MIN_SCORE_TO_ENTER, bool):
        if not 0 <= MIN_SCORE_TO_ENTER <= 100:
            errors.append("MIN_SCORE_TO_ENTER must be between 0 and 100.")

    # PAPER ACCOUNT
    numeric_settings = {
        "INITIAL_BALANCE": INITIAL_BALANCE,
        "RISK_PER_TRADE_PCT": RISK_PER_TRADE_PCT,
        "MAX_ALLOCATION_PCT": MAX_ALLOCATION_PCT,
        "FEE_RATE": FEE_RATE,
        "SIMULATED_SLIPPAGE_BPS": SIMULATED_SLIPPAGE_BPS,
        "STOP_ATR_MULTIPLIER": STOP_ATR_MULTIPLIER,
        "TARGET_R_MULTIPLIER": TARGET_R_MULTIPLIER,
    }

    for name, value in numeric_settings.items():
        if not _is_finite_number(value):
            errors.append(f"{name} must be a finite number.")

    if _is_finite_number(INITIAL_BALANCE) and INITIAL_BALANCE <= 0:
        errors.append("INITIAL_BALANCE must be positive.")

    if _is_finite_number(RISK_PER_TRADE_PCT):
        if not 0 < RISK_PER_TRADE_PCT <= 0.01:
            errors.append("RISK_PER_TRADE_PCT must be in (0, 0.01].")

    if _is_finite_number(MAX_ALLOCATION_PCT):
        if not 0 < MAX_ALLOCATION_PCT <= 1:
            errors.append("MAX_ALLOCATION_PCT must be in (0, 1].")

    if _is_finite_number(FEE_RATE):
        if not 0 <= FEE_RATE < 1:
            errors.append("FEE_RATE must be in [0, 1).")

    if _is_finite_number(SIMULATED_SLIPPAGE_BPS):
        if not 0 <= SIMULATED_SLIPPAGE_BPS < 10000:
            errors.append("SIMULATED_SLIPPAGE_BPS must be in [0, 10000).")

    if _is_finite_number(STOP_ATR_MULTIPLIER):
        if STOP_ATR_MULTIPLIER <= 0:
            errors.append("STOP_ATR_MULTIPLIER must be positive.")

    if _is_finite_number(TARGET_R_MULTIPLIER):
        if TARGET_R_MULTIPLIER <= 0:
            errors.append("TARGET_R_MULTIPLIER must be positive.")

    # AI COUNCIL
    if not _valid_https_url(HF_API_URL):
        errors.append("HF_API_URL must be a valid HTTPS URL.")

    if (
        isinstance(AI_REQUEST_TIMEOUT_SECONDS, bool)
        or not isinstance(AI_REQUEST_TIMEOUT_SECONDS, (int, float))
        or not _is_finite_number(AI_REQUEST_TIMEOUT_SECONDS)
        or AI_REQUEST_TIMEOUT_SECONDS <= 0
    ):
        errors.append("AI_REQUEST_TIMEOUT_SECONDS must be positive.")

    if (
        isinstance(AI_MAX_CONCURRENT_REQUESTS, bool)
        or not isinstance(AI_MAX_CONCURRENT_REQUESTS, int)
        or AI_MAX_CONCURRENT_REQUESTS < 1
    ):
        errors.append("AI_MAX_CONCURRENT_REQUESTS must be at least 1.")

    if (
        isinstance(AI_MIN_VALID_MODELS, bool)
        or not isinstance(AI_MIN_VALID_MODELS, int)
        or AI_MIN_VALID_MODELS < 1
    ):
        errors.append("AI_MIN_VALID_MODELS must be at least 1.")

    if not _is_finite_number(AI_MIN_AGREEMENT_RATIO):
        errors.append("AI_MIN_AGREEMENT_RATIO must be finite.")
    elif not 0.5 < AI_MIN_AGREEMENT_RATIO <= 1:
        errors.append("AI_MIN_AGREEMENT_RATIO must be in (0.5, 1].")

    # NEWS
    if NEWS_REFRESH_SECONDS <= 0:
        errors.append("NEWS_REFRESH_SECONDS must be positive.")

    if NEWS_MAX_ITEMS < 1:
        errors.append("NEWS_MAX_ITEMS must be at least 1.")

    if NEWS_REQUEST_TIMEOUT_SECONDS <= 0:
        errors.append("NEWS_REQUEST_TIMEOUT_SECONDS must be positive.")

    # HTTP
    if HTTP_TIMEOUT_SECONDS <= 0:
        errors.append("HTTP_TIMEOUT_SECONDS must be positive.")

    if HTTP_CONNECT_TIMEOUT_SECONDS <= 0:
        errors.append("HTTP_CONNECT_TIMEOUT_SECONDS must be positive.")

    if HTTP_MAX_CONNECTIONS < 1:
        errors.append("HTTP_MAX_CONNECTIONS must be at least 1.")

    if HTTP_RETRY_ATTEMPTS < 0:
        errors.append("HTTP_RETRY_ATTEMPTS cannot be negative.")

    # LOGGING
    if LOG_LEVEL not in {
        "CRITICAL",
        "ERROR",
        "WARNING",
        "INFO",
        "DEBUG",
    }:
        errors.append("LOG_LEVEL is invalid.")

    # RESULT
    if errors:
        raise ValueError(
            "Invalid application configuration:\n- "
            + "\n- ".join(errors)
        )

    return True

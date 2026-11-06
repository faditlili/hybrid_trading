import logging
import math

import pandas as pd


logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
]

MIN_CANDLES = 61


# ============================================================
# VALIDATION
# ============================================================

def _is_valid(value):
    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _validate_data(df):
    if not isinstance(df, pd.DataFrame):
        return None

    if not all(col in df.columns for col in REQUIRED_COLUMNS):
        return None

    if len(df) < MIN_CANDLES:
        return None

    data = df[REQUIRED_COLUMNS].copy()

    for col in REQUIRED_COLUMNS:
        data[col] = pd.to_numeric(
            data[col],
            errors="coerce",
        )

    if data.isna().any().any():
        return None

    if not all(
        math.isfinite(float(v))
        for v in data.to_numpy().flatten()
    ):
        return None

    if (data["open"] <= 0).any():
        return None

    if (data["high"] <= 0).any():
        return None

    if (data["low"] <= 0).any():
        return None

    if (data["close"] <= 0).any():
        return None

    if (data["volume"] < 0).any():
        return None

    if (data["high"] < data["low"]).any():
        return None

    if (
        data["high"]
        < data[["open", "close"]].max(axis=1)
    ).any():
        return None

    if (
        data["low"]
        > data[["open", "close"]].min(axis=1)
    ).any():
        return None

    return data.reset_index(drop=True)


# ============================================================
# INDICATORS
# ============================================================

def _calculate_rsi(close, period=14):
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))

    rsi = 100 - (100 / (1 + rs))

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain > 0),
        100,
    )

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain == 0),
        50,
    )

    return rsi


def _calculate_macd(close):
    ema12 = close.ewm(
        span=12,
        adjust=False,
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False,
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False,
    ).mean()

    histogram = macd - signal

    return macd, signal, histogram


def _calculate_atr(data, period=14):
    previous_close = data["close"].shift(1)

    tr = pd.concat(
        [
            data["high"] - data["low"],
            (data["high"] - previous_close).abs(),
            (data["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False,
    ).mean()


# ============================================================
# CANDLE PATTERNS
# ============================================================

def _detect_candle_patterns(data):
    current = data.iloc[-1]
    previous = data.iloc[-2]

    body = abs(current["close"] - current["open"])

    candle_range = current["high"] - current["low"]

    if candle_range <= 0:
        return []

    upper_shadow = (
        current["high"]
        - max(current["open"], current["close"])
    )

    lower_shadow = (
        min(current["open"], current["close"])
        - current["low"]
    )

    bullish = current["close"] > current["open"]
    bearish = current["close"] < current["open"]

    patterns = []

    # Doji
    if body <= candle_range * 0.10:
        patterns.append("DOJI")

    # Hammer
    if (
        lower_shadow >= body * 2
        and upper_shadow <= candle_range * 0.20
        and body > 0
    ):
        patterns.append("HAMMER")

    # Shooting Star
    if (
        upper_shadow >= body * 2
        and lower_shadow <= candle_range * 0.20
        and body > 0
    ):
        patterns.append("SHOOTING_STAR")

    # Bullish Engulfing
    if (
        bullish
        and previous["close"] < previous["open"]
        and current["open"] <= previous["close"]
        and current["close"] >= previous["open"]
    ):
        patterns.append("BULLISH_ENGULFING")

    # Bearish Engulfing
    if (
        bearish
        and previous["close"] > previous["open"]
        and current["open"] >= previous["close"]
        and current["close"] <= previous["open"]
    ):
        patterns.append("BEARISH_ENGULFING")

    return patterns


# ============================================================
# MARKET ANALYSIS
# ============================================================

def calculate_indicators(df):

    data = _validate_data(df)

    if data is None:
        logger.warning("Invalid OHLCV market data")
        return None

    try:
        close = data["close"]

        # EMA
        for period in [9, 21, 50, 200]:
            data[f"ema_{period}"] = close.ewm(
                span=period,
                adjust=False,
            ).mean()

        # RSI
        data["rsi"] = _calculate_rsi(close)

        # MACD
        (
            data["macd"],
            data["macd_signal"],
            data["macd_histogram"],
        ) = _calculate_macd(close)

        # ATR
        data["atr"] = _calculate_atr(data)

        # Bollinger Bands
        middle = close.rolling(20).mean()
        std = close.rolling(20).std(ddof=0)

        data["bb_middle"] = middle
        data["bb_upper"] = middle + (2 * std)
        data["bb_lower"] = middle - (2 * std)

        # Volume analysis
        data["volume_sma"] = (
            data["volume"].rolling(20).mean()
        )

        data["volume_ratio"] = (
            data["volume"]
            / data["volume_sma"].replace(0, float("nan"))
        )

        # Candle patterns
        patterns = _detect_candle_patterns(data)

        # Market trend
        latest = data.iloc[-1]

        if (
            latest["ema_9"] > latest["ema_21"]
            and latest["ema_21"] > latest["ema_50"]
            and latest["close"] > latest["ema_50"]
        ):
            trend = "BULLISH"

        elif (
            latest["ema_9"] < latest["ema_21"]
            and latest["ema_21"] < latest["ema_50"]
            and latest["close"] < latest["ema_50"]
        ):
            trend = "BEARISH"

        else:
            trend = "SIDEWAYS"

        # Momentum
        if latest["rsi"] >= 55:
            momentum = "BULLISH"

        elif latest["rsi"] <= 45:
            momentum = "BEARISH"

        else:
            momentum = "NEUTRAL"

        # MACD direction
        if latest["macd"] > latest["macd_signal"]:
            macd_trend = "BULLISH"

        elif latest["macd"] < latest["macd_signal"]:
            macd_trend = "BEARISH"

        else:
            macd_trend = "NEUTRAL"

        # Final result
        result = {
            "data": data,
            "trend": trend,
            "momentum": momentum,
            "macd_trend": macd_trend,
            "patterns": patterns,
            "close": float(latest["close"]),
            "rsi": float(latest["rsi"]),
            "atr": float(latest["atr"]),
            "ema_9": float(latest["ema_9"]),
            "ema_21": float(latest["ema_21"]),
            "ema_50": float(latest["ema_50"]),
            "ema_200": float(latest["ema_200"]),
            "macd": float(latest["macd"]),
            "macd_signal": float(latest["macd_signal"]),
            "macd_histogram": float(
                latest["macd_histogram"]
            ),
            "bb_upper": float(latest["bb_upper"]),
            "bb_middle": float(latest["bb_middle"]),
            "bb_lower": float(latest["bb_lower"]),
            "volume_ratio": (
                float(latest["volume_ratio"])
                if _is_valid(latest["volume_ratio"])
                else 0.0
            ),
        }

        for key, value in result.items():
            if key == "data":
                continue

            if isinstance(value, float) and not _is_valid(value):
                logger.warning(
                    "Invalid indicator result: %s",
                    key,
                )
                return None

        return result

    except Exception:
        logger.exception("Technical analysis failed")
        return None

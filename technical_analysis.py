"""AI QUANT 4.0 - Technical Analysis.
OHLCV validation and indicator calculations.
Paper trading analysis only.
"""

import math

import numpy as np
import pandas as pd


REQUIRED = (
    "open",
    "high",
    "low",
    "close",
    "volume",
)

MIN_CANDLES = 200

TIME_COLUMNS = (
    "timestamp",
    "time",
    "open_time",
    "openTime",
    "ts",
)


def _finite_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def validate_ohlcv(rows):
    """Validate and normalize OHLCV candles."""

    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()
    else:
        try:
            frame = pd.DataFrame(rows)
        except Exception as exc:
            raise ValueError("Invalid OHLCV input") from exc

    if frame.empty:
        raise ValueError("No candle data provided")

    if not frame.columns.is_unique:
        raise ValueError("Duplicate column names")

    missing = [
        col for col in REQUIRED
        if col not in frame.columns
    ]

    if missing:
        raise ValueError(
            f"Missing OHLCV columns: {missing}"
        )

    # Sort by timestamp when available.
    time_column = next(
        (col for col in TIME_COLUMNS if col in frame.columns),
        None,
    )

    if time_column is not None:
        timestamps = frame[time_column]

        numeric_time = pd.to_numeric(
            timestamps,
            errors="coerce",
        )

        if numeric_time.notna().all():
            frame["_sort_time"] = numeric_time
        else:
            parsed_time = pd.to_datetime(
                timestamps,
                utc=True,
                errors="coerce",
            )

            if parsed_time.isna().any():
                raise ValueError("Invalid candle timestamps")

            frame["_sort_time"] = parsed_time

        frame = (
            frame.sort_values("_sort_time", kind="stable")
            .drop_duplicates(subset=[time_column], keep="last")
            .drop(columns=["_sort_time"])
        )

    # Keep required OHLCV columns.
    frame = frame.loc[:, REQUIRED].copy()

    for column in REQUIRED:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    # Remove invalid numeric values.
    frame = (
        frame.replace([np.inf, -np.inf], np.nan)
        .dropna(subset=list(REQUIRED))
    )

    # Validate prices and volume.
    valid_values = (
        (frame["open"] > 0)
        & (frame["high"] > 0)
        & (frame["low"] > 0)
        & (frame["close"] > 0)
        & (frame["volume"] >= 0)
    )

    frame = frame.loc[valid_values].copy()

    # Validate candle structure.
    valid_structure = (
        (frame["high"] >= frame["open"])
        & (frame["high"] >= frame["close"])
        & (frame["high"] >= frame["low"])
        & (frame["low"] <= frame["open"])
        & (frame["low"] <= frame["close"])
    )

    frame = frame.loc[valid_structure].copy()

    if len(frame) < MIN_CANDLES:
        raise ValueError(
            f"At least {MIN_CANDLES} valid candles required; "
            f"received {len(frame)}"
        )

    return frame.reset_index(drop=True)


def calculate_indicators(rows):
    """Calculate EMA, RSI, MACD, ATR and volume indicators."""

    frame = validate_ohlcv(rows)

    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]

    # EMA
    def ema(period):
        return close.ewm(
            span=period,
            adjust=False,
            min_periods=period,
        ).mean()

    ema9 = ema(9)
    ema21 = ema(21)
    ema50 = ema(50)
    ema200 = ema(200)

    # RSI - Wilder smoothing
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    average_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14,
    ).mean()

    average_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14,
    ).mean()

    rs = average_gain / average_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    rsi = rsi.mask(
        (average_loss == 0) & (average_gain > 0),
        100.0,
    )

    rsi = rsi.mask(
        (average_gain == 0) & (average_loss > 0),
        0.0,
    )

    rsi = rsi.mask(
        (average_gain == 0) & (average_loss == 0),
        50.0,
    )

    # MACD
    fast = close.ewm(
        span=12,
        adjust=False,
        min_periods=12,
    ).mean()

    slow = close.ewm(
        span=26,
        adjust=False,
        min_periods=26,
    ).mean()

    macd = fast - slow

    macd_signal = macd.ewm(
        span=9,
        adjust=False,
        min_periods=9,
    ).mean()

    # ATR - Wilder smoothing
    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14,
    ).mean()

    # Volume
    volume_avg = volume.rolling(
        window=20,
        min_periods=20,
    ).mean()

    # Safe output conversion
    def value(series):
        result = series.iloc[-1]

        if not _finite_number(result):
            return None

        return float(result)

    result = {
        "price": value(close),

        "ema9": value(ema9),
        "ema21": value(ema21),
        "ema50": value(ema50),
        "ema200": value(ema200),

        "rsi": value(rsi),

        "macd": value(macd),
        "macd_signal": value(macd_signal),

        "atr": value(atr),

        "volume": value(volume),
        "volume_avg": value(volume_avg),

        "high_20": value(high.tail(20).max()),
        "low_20": value(low.tail(20).min()),

        "candles": len(frame),
    }

    # Final validation
    required_indicators = (
        "price",
        "ema9",
        "ema21",
        "ema50",
        "ema200",
        "rsi",
        "macd",
        "macd_signal",
        "atr",
    )

    for name in required_indicators:
        if result[name] is None:
            raise ValueError(
                f"Indicator calculation failed: {name}"
            )

    if result["price"] <= 0:
        raise ValueError("Invalid calculated price")

    if result["atr"] <= 0:
        raise ValueError("Invalid calculated ATR")

    if not 0 <= result["rsi"] <= 100:
        raise ValueError("Invalid calculated RSI")

    return result

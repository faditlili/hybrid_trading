
"""Dependency-light OHLCV validation and indicator calculations.

Calculates EMA, RSI, MACD, ATR and volume indicators.
No trading or exchange order functionality.
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


# --------------------------------------------------
# OHLCV validation
# --------------------------------------------------

def validate_ohlcv(rows):
    """Validate and normalize historical OHLCV candles."""

    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()

    else:
        try:
            frame = pd.DataFrame(rows)
        except Exception as exc:
            raise ValueError(
                "Invalid OHLCV input"
            ) from exc

    if frame.empty:
        raise ValueError("No candle data provided")

    missing = [
        column
        for column in REQUIRED
        if column not in frame.columns
    ]

    if missing:
        raise ValueError(
            f"Missing OHLCV columns: {missing}"
        )

    frame = frame.loc[:, REQUIRED].copy()

    # Convert all OHLCV columns to numeric values.
    frame = frame.apply(
        pd.to_numeric,
        errors="coerce",
    )

    # Remove invalid and infinite values.
    frame = (
        frame.replace(
            [np.inf, -np.inf],
            np.nan,
        )
        .dropna()
    )

    # Prices must be positive; volume cannot be negative.
    frame = frame[
        (frame["open"] > 0)
        & (frame["high"] > 0)
        & (frame["low"] > 0)
        & (frame["close"] > 0)
        & (frame["volume"] >= 0)
    ]

    # Validate candle structure.
    frame = frame[
        (
            frame["high"]
            >= frame[
                ["open", "close", "low"]
            ].max(axis=1)
        )
        & (
            frame["low"]
            <= frame[
                ["open", "close", "high"]
            ].min(axis=1)
        )
    ]

    # EMA200 requires at least 200 valid observations.
    if len(frame) < MIN_CANDLES:
        raise ValueError(
            f"At least {MIN_CANDLES} valid candles are required; "
            f"received {len(frame)}"
        )

    frame = frame.reset_index(drop=True)

    return frame


# --------------------------------------------------
# Indicator calculations
# --------------------------------------------------

def calculate_indicators(rows):
    """Calculate technical indicators from OHLCV candles."""

    frame = validate_ohlcv(rows)

    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]

    # --------------------------------------------------
    # Exponential moving averages
    # --------------------------------------------------

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

    # --------------------------------------------------
    # RSI - Wilder smoothing
    # --------------------------------------------------

    delta = close.diff()

    gain = delta.clip(
        lower=0,
    )

    loss = -delta.clip(
        upper=0,
    )

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

    rs = (
        average_gain
        / average_loss.replace(0, np.nan)
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    # Handle zero-loss and zero-gain cases.
    rsi = rsi.mask(
        (average_loss == 0) & (average_gain > 0),
        100.0,
    )

    rsi = rsi.mask(
        (average_gain == 0) & (average_loss > 0),
        0.0,
    )

    # Completely flat market.
    rsi = rsi.mask(
        (average_gain == 0) & (average_loss == 0),
        50.0,
    )

    # --------------------------------------------------
    # MACD
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Average True Range
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Volume
    # --------------------------------------------------

    volume_avg = volume.rolling(
        window=20,
        min_periods=20,
    ).mean()

    # --------------------------------------------------
    # Safe output conversion
    # --------------------------------------------------

    def value(series):
        result = series.iloc[-1]

        if pd.isna(result):
            return None

        try:
            result = float(result)
        except (TypeError, ValueError, OverflowError):
            return None

        if not math.isfinite(result):
            return None

        return result

    # --------------------------------------------------
    # Final indicator validation
    # --------------------------------------------------

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

        "high_20": value(
            high.tail(20).max()
        ),

        "low_20": value(
            low.tail(20).min()
        ),

        "candles": len(frame),
    }

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

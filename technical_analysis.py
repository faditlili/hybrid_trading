"""Dependency-light OHLCV validation and indicator calculations."""

import math
import pandas as pd
import numpy as np

REQUIRED = ("open", "high", "low", "close", "volume")


def validate_ohlcv(rows):
    if isinstance(rows, pd.DataFrame):
        frame = rows.copy()
    else:
        frame = pd.DataFrame(rows, columns=REQUIRED)

    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")

    frame = (
        frame.loc[:, REQUIRED]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )

    frame = frame[
        (frame["open"] > 0)
        & (frame["high"] > 0)
        & (frame["low"] > 0)
        & (frame["close"] > 0)
        & (frame["volume"] >= 0)
    ]

    frame = frame[
        (frame["high"] >= frame[["open", "close", "low"]].max(axis=1))
        & (frame["low"] <= frame[["open", "close", "high"]].min(axis=1))
    ]

    if len(frame) < 60:
        raise ValueError("At least 60 valid candles are required")

    return frame.reset_index(drop=True)


def calculate_indicators(rows):
    frame = validate_ohlcv(rows)
    close = frame["close"]

    def ema(period):
        return close.ewm(
            span=period,
            adjust=False,
            min_periods=period
        ).mean()

    ema9 = ema(9)
    ema21 = ema(21)
    ema50 = ema(50)
    ema200 = ema(200)

    # RSI
    delta = close.diff()

    gain = delta.clip(lower=0).ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    loss = (-delta.clip(upper=0)).ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # Handle zero-loss and zero-gain cases.
    rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
    rsi = rsi.mask((gain == 0) & (loss > 0), 0.0)
    rsi = rsi.mask((gain == 0) & (loss == 0), 50.0)

    # MACD
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()

    macd = fast - slow
    signal = macd.ewm(span=9, adjust=False).mean()

    # ATR
    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    # Volume
    volume_avg = frame["volume"].rolling(20).mean()

    def value(series):
        result = series.iloc[-1]

        if pd.isna(result):
            return None

        result = float(result)

        return result if math.isfinite(result) else None

    return {
        "price": value(close),
        "ema9": value(ema9),
        "ema21": value(ema21),
        "ema50": value(ema50),
        "ema200": value(ema200),
        "rsi": value(rsi),
        "macd": value(macd),
        "macd_signal": value(signal),
        "atr": value(atr),
        "volume": value(frame["volume"]),
        "volume_avg": value(volume_avg),
        "high_20": value(frame["high"].tail(20).max()),
        "low_20": value(frame["low"].tail(20).min()),
        "candles": len(frame)
    }

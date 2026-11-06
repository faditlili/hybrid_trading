import math
from datetime import datetime, timezone

import pandas as pd


def _is_valid(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def calculate_indicators(df):

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    if df is None or len(df) < 61:
        return None

    if any(column not in df.columns for column in required):
        return None

    data = df.copy()

    for column in required:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna(subset=required)

    # استعمال الشموع المغلقة فقط
    if "close_time" in data.columns:
        now_ms = datetime.now(timezone.utc).timestamp() * 1000

        data["close_time"] = pd.to_numeric(
            data["close_time"],
            errors="coerce"
        )

        data = data[
            data["close_time"] < now_ms
        ]

    else:
        data = data.iloc[:-1]

    data = data.reset_index(drop=True)

    if len(data) < 60:
        return None

    close = data["close"]
    high = data["high"]
    low = data["low"]
    volume = data["volume"]

    if (close <= 0).any():
        return None

    # EMA
    ema9 = close.ewm(
        span=9,
        adjust=False
    ).mean()

    ema21 = close.ewm(
        span=21,
        adjust=False
    ).mean()

    ema50 = close.ewm(
        span=50,
        adjust=False
    ).mean()

    # RSI 14
    delta = close.diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    avg_gain = gains.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = losses.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))

    rsi = 100 - (100 / (1 + rs))

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain > 0),
        100
    )

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain == 0),
        50
    )

    # ATR 14
    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr = tr.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    # MACD
    ema12 = close.ewm(
        span=12,
        adjust=False
    ).mean()

    ema26 = close.ewm(
        span=26,
        adjust=False
    ).mean()

    macd = ema12 - ema26

    signal = macd.ewm(
        span=9,
        adjust=False
    ).mean()

    # Average volume
    volume_avg = volume.rolling(
        window=20
    ).mean()

    values = {
        "price": close.iloc[-1],
        "ema9": ema9.iloc[-1],
        "ema21": ema21.iloc[-1],
        "ema50": ema50.iloc[-1],
        "rsi": rsi.iloc[-1],
        "atr": atr.iloc[-1],
        "macd": macd.iloc[-1],
        "macd_signal": signal.iloc[-1],
        "volume": volume.iloc[-1],
        "volume_avg": volume_avg.iloc[-1],
        "previous_close": close.iloc[-2]
    }

    if not all(_is_valid(value) for value in values.values()):
        return None

    result = {
        key: float(value)
        for key, value in values.items()
    }

    if result["atr"] <= 0:
        return None

    return result

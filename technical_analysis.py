import pandas as pd


def calculate_indicators(candles):
    if candles is None or len(candles) < 60:
        raise ValueError("Not enough candle data")

    df = candles.copy()

    close = df["close"]
    high = df["high"]
    low = df["low"]

    df["ema9"] = close.ewm(span=9, adjust=False).mean()
    df["ema21"] = close.ewm(span=21, adjust=False).mean()
    df["ema50"] = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    df["atr"] = tr.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False
    ).mean()

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(
        span=9,
        adjust=False
    ).mean()

    df["volume_avg"] = df["volume"].rolling(20).mean()

    last = df.iloc[-1]
    previous = df.iloc[-2]

    result = {
        "price": float(last["close"]),
        "ema9": float(last["ema9"]),
        "ema21": float(last["ema21"]),
        "ema50": float(last["ema50"]),
        "rsi": float(last["rsi"]),
        "atr": float(last["atr"]),
        "macd": float(last["macd"]),
        "macd_signal": float(last["macd_signal"]),
        "volume": float(last["volume"]),
        "volume_avg": float(last["volume_avg"]),
        "previous_close": float(previous["close"])
    }

    if any(
        pd.isna(value)
        for value in result.values()
    ):
        raise ValueError("Indicator calculation returned invalid values")

    if result["atr"] <= 0:
        raise ValueError("Invalid ATR value")

    return result

import math
import logging

import pandas as pd


logger = logging.getLogger(__name__)


REQUIRED_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume"
]


def _is_valid(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def calculate_indicators(df):

    try:

        if df is None or not isinstance(df, pd.DataFrame):
            return None

        if len(df) < 61:
            return None

        if not all(
            column in df.columns
            for column in REQUIRED_COLUMNS
        ):
            return None

        data = df.copy()

        # Convert OHLCV columns to numeric values
        for column in REQUIRED_COLUMNS:
            data[column] = pd.to_numeric(
                data[column],
                errors="coerce"
            )

        # Remove missing and infinite OHLCV values
        for column in REQUIRED_COLUMNS:
            data = data[
                data[column].map(_is_valid)
            ]

        data = data.dropna(
            subset=REQUIRED_COLUMNS
        )

        # Sort candles chronologically
        if "open_time" in data.columns:

            data["open_time"] = pd.to_numeric(
                data["open_time"],
                errors="coerce"
            )

            data = data.dropna(
                subset=["open_time"]
            )

            data = data.sort_values(
                "open_time"
            )

            data = data.drop_duplicates(
                subset=["open_time"],
                keep="last"
            )

        elif "close_time" in data.columns:

            if pd.api.types.is_datetime64_any_dtype(
                data["close_time"]
            ):

                if data["close_time"].dt.tz is None:
                    data["close_time"] = (
                        data["close_time"].dt.tz_localize("UTC")
                    )
                else:
                    data["close_time"] = (
                        data["close_time"].dt.tz_convert("UTC")
                    )

            else:

                close_time_numeric = pd.to_numeric(
                    data["close_time"],
                    errors="coerce"
                )

                data["close_time"] = pd.to_datetime(
                    close_time_numeric,
                    unit="ms",
                    utc=True,
                    errors="coerce"
                )

            data = data.dropna(
                subset=["close_time"]
            )

            data = data.sort_values(
                "close_time"
            )

            data = data.drop_duplicates(
                subset=["close_time"],
                keep="last"
            )

        else:

            # Without candle timestamps, preserve the supplied order.
            data = data[~data.index.duplicated(keep="last")]

        # Exclude incomplete candles
        if "close_time" in data.columns:

            now = pd.Timestamp.now(tz="UTC")

            data = data[
                data["close_time"] < now
            ]

        else:

            # Conservatively exclude the final candle
            data = data.iloc[:-1]

        if len(data) < 60:
            return None

        # Validate OHLCV relationships
        valid_ohlc = (
            (data["open"] > 0)
            & (data["high"] > 0)
            & (data["low"] > 0)
            & (data["close"] > 0)
            & (data["volume"] >= 0)
            & (data["high"] >= data["low"])
            & (data["high"] >= data["open"])
            & (data["high"] >= data["close"])
            & (data["low"] <= data["open"])
            & (data["low"] <= data["close"])
        )

        data = data.loc[valid_ohlc].copy()

        if len(data) < 60:
            return None

        # EMA indicators
        data["ema9"] = data["close"].ewm(
            span=9,
            adjust=False
        ).mean()

        data["ema21"] = data["close"].ewm(
            span=21,
            adjust=False
        ).mean()

        data["ema50"] = data["close"].ewm(
            span=50,
            adjust=False
        ).mean()

        # RSI
        delta = data["close"].diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        ).mean()

        avg_loss = loss.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        ).mean()

        rs = avg_gain / avg_loss.replace(
            0,
            float("nan")
        )

        data["rsi"] = 100 - (
            100 / (1 + rs)
        )

        # Handle zero-loss cases
        data.loc[
            (avg_loss == 0) & (avg_gain > 0),
            "rsi"
        ] = 100

        data.loc[
            (avg_loss == 0) & (avg_gain == 0),
            "rsi"
        ] = 50

        # ATR
        previous_close = data["close"].shift(1)

        tr1 = data["high"] - data["low"]

        tr2 = (
            data["high"] - previous_close
        ).abs()

        tr3 = (
            data["low"] - previous_close
        ).abs()

        true_range = pd.concat(
            [tr1, tr2, tr3],
            axis=1
        ).max(axis=1)

        data["atr"] = true_range.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14
        ).mean()

        # MACD
        ema12 = data["close"].ewm(
            span=12,
            adjust=False
        ).mean()

        ema26 = data["close"].ewm(
            span=26,
            adjust=False
        ).mean()

        data["macd"] = ema12 - ema26

        data["macd_signal"] = data["macd"].ewm(
            span=9,
            adjust=False
        ).mean()

        # Average volume
        data["volume_avg"] = data["volume"].rolling(
            window=20,
            min_periods=20
        ).mean()

        latest = data.iloc[-1]
        previous = data.iloc[-2]

        result = {
            "price": float(latest["close"]),
            "ema9": float(latest["ema9"]),
            "ema21": float(latest["ema21"]),
            "ema50": float(latest["ema50"]),
            "rsi": float(latest["rsi"]),
            "atr": float(latest["atr"]),
            "macd": float(latest["macd"]),
            "macd_signal": float(latest["macd_signal"]),
            "volume": float(latest["volume"]),
            "volume_avg": float(latest["volume_avg"]),
            "previous_close": float(previous["close"])
        }

        # Validate all final indicators
        if not all(
            _is_valid(value)
            for value in result.values()
        ):
            return None

        if result["price"] <= 0:
            return None

        if result["atr"] <= 0:
            return None

        if not 0 <= result["rsi"] <= 100:
            return None

        if result["volume"] < 0:
            return None

        if result["volume_avg"] < 0:
            return None

        return result

    except Exception:

        logger.exception(
            "Technical analysis failed"
        )

        return None

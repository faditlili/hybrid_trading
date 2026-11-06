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


def _is_valid(value):

    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))

    except (TypeError, ValueError, OverflowError):
        return False


def _validate_ohlcv(data):

    if data.empty:
        return False

    required = data[REQUIRED_COLUMNS]

    if required.isna().any().any():
        return False

    for column in REQUIRED_COLUMNS:

        values = required[column].to_numpy(
            dtype=float
        )

        if not all(
            math.isfinite(float(value))
            for value in values
        ):
            return False

    invalid = (
        (data["open"] <= 0)
        | (data["high"] <= 0)
        | (data["low"] <= 0)
        | (data["close"] <= 0)
        | (data["volume"] < 0)
        | (data["high"] < data["low"])
        | (data["high"] < data["open"])
        | (data["high"] < data["close"])
        | (data["low"] > data["open"])
        | (data["low"] > data["close"])
    )

    return not invalid.any()


def _prepare_data(df):

    if not isinstance(df, pd.DataFrame):
        return None

    if len(df) < MIN_CANDLES:
        return None

    if not all(
        column in df.columns
        for column in REQUIRED_COLUMNS
    ):
        return None

    data = df.copy()

    for column in REQUIRED_COLUMNS:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=REQUIRED_COLUMNS
    )

    # Sort and remove duplicate candles.
    if "open_time" in data.columns:

        data["open_time"] = pd.to_numeric(
            data["open_time"],
            errors="coerce",
        )

        data = data.dropna(
            subset=["open_time"]
        )

        data = data.sort_values(
            "open_time"
        )

        data = data.drop_duplicates(
            subset=["open_time"],
            keep="last",
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
                errors="coerce",
            )

            data["close_time"] = pd.to_datetime(
                close_time_numeric,
                unit="ms",
                utc=True,
                errors="coerce",
            )

        data = data.dropna(
            subset=["close_time"]
        )

        data = data.sort_values(
            "close_time"
        )

        data = data.drop_duplicates(
            subset=["close_time"],
            keep="last",
        )

    else:

        data = data[
            ~data.index.duplicated(keep="last")
        ]

    # Exclude incomplete candles.
    if "close_time" in data.columns:

        now = pd.Timestamp.now(
            tz="UTC"
        )

        data = data[
            data["close_time"] < now
        ]

    else:

        # Without timestamps, conservatively exclude
        # the final potentially incomplete candle.
        data = data.iloc[:-1]

    data = data.reset_index(
        drop=True
    )

    if len(data) < 60:
        return None

    if not _validate_ohlcv(data):
        return None

    return data


def calculate_indicators(df):

    try:

        data = _prepare_data(df)

        if data is None:
            return None

        # ====================================================
        # EMA
        # ====================================================

        data["ema9"] = data["close"].ewm(
            span=9,
            adjust=False,
        ).mean()

        data["ema21"] = data["close"].ewm(
            span=21,
            adjust=False,
        ).mean()

        data["ema50"] = data["close"].ewm(
            span=50,
            adjust=False,
        ).mean()

        # ====================================================
        # RSI - Wilder smoothing
        # ====================================================

        delta = data["close"].diff()

        gain = delta.clip(
            lower=0
        )

        loss = -delta.clip(
            upper=0
        )

        avg_gain = gain.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14,
        ).mean()

        avg_loss = loss.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14,
        ).mean()

        rs = avg_gain / avg_loss.replace(
            0,
            float("nan"),
        )

        data["rsi"] = 100 - (
            100 / (1 + rs)
        )

        # No losses: RSI = 100.
        data.loc[
            (avg_loss == 0) & (avg_gain > 0),
            "rsi",
        ] = 100

        # No gains and no losses: neutral RSI.
        data.loc[
            (avg_loss == 0) & (avg_gain == 0),
            "rsi",
        ] = 50

        # ====================================================
        # ATR - Wilder smoothing
        # ====================================================

        previous_close = data["close"].shift(1)

        tr1 = (
            data["high"] - data["low"]
        )

        tr2 = (
            data["high"] - previous_close
        ).abs()

        tr3 = (
            data["low"] - previous_close
        ).abs()

        true_range = pd.concat(
            [tr1, tr2, tr3],
            axis=1,
        ).max(axis=1)

        data["atr"] = true_range.ewm(
            alpha=1 / 14,
            adjust=False,
            min_periods=14,
        ).mean()

        # ====================================================
        # MACD
        # ====================================================

        ema12 = data["close"].ewm(
            span=12,
            adjust=False,
        ).mean()

        ema26 = data["close"].ewm(
            span=26,
            adjust=False,
        ).mean()

        data["macd"] = ema12 - ema26

        data["macd_signal"] = data["macd"].ewm(
            span=9,
            adjust=False,
        ).mean()

        # ====================================================
        # VOLUME
        # ====================================================

        # Exclude current candle from the reference average.
        data["volume_avg"] = (
            data["volume"]
            .shift(1)
            .rolling(
                window=20,
                min_periods=20,
            )
            .mean()
        )

        # ====================================================
        # FINAL VALUES
        # ====================================================

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
            "previous_close": float(previous["close"]),
        }

        # ====================================================
        # VALIDATION
        # ====================================================

        if not all(
            _is_valid(value)
            for value in result.values()
        ):
            return None

        if result["price"] <= 0:
            return None

        if result["previous_close"] <= 0:
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

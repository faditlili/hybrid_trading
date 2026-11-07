
"""Transparent deterministic scoring for AI QUANT.

Educational paper simulation only.
AI output is advisory and cannot bypass quantitative safety gates.
"""

import math
import config


TIMEFRAMES = ("15m", "1h", "4h")

REQUIRED_INDICATORS = (
    "price",
    "ema9",
    "ema21",
    "ema50",
    "rsi",
    "macd",
    "macd_signal",
    "atr",
)


# --------------------------------------------------
# Validation helpers
# --------------------------------------------------

def valid_number(value):
    """Return True only for finite numeric values."""

    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))

    except (TypeError, ValueError, OverflowError):
        return False


def validate_timeframe(data):
    """Validate required indicators and return an error or None."""

    if not isinstance(data, dict):
        return "invalid timeframe data"

    for key in REQUIRED_INDICATORS:

        if not valid_number(data.get(key)):
            return f"invalid or missing indicator: {key}"

    price = float(data["price"])
    ema9 = float(data["ema9"])
    ema21 = float(data["ema21"])
    ema50 = float(data["ema50"])
    rsi = float(data["rsi"])
    atr = float(data["atr"])

    if price <= 0:
        return "invalid price"

    if atr <= 0:
        return "invalid ATR"

    if min(ema9, ema21, ema50) <= 0:
        return "invalid EMA values"

    if not 0 <= rsi <= 100:
        return "RSI outside valid range"

    return None


# --------------------------------------------------
# Timeframe scoring
# --------------------------------------------------

def score_timeframe(data):
    """Calculate a deterministic score for one timeframe."""

    score = 0
    reasons = []

    validation_error = validate_timeframe(data)

    if validation_error:
        return 0, [validation_error]

    price = float(data["price"])
    ema9 = float(data["ema9"])
    ema21 = float(data["ema21"])
    ema50 = float(data["ema50"])
    rsi = float(data["rsi"])
    macd = float(data["macd"])
    macd_signal = float(data["macd_signal"])

    # Short-term trend.
    if ema9 > ema21:
        score += 20
        reasons.append("short trend positive")

    # Medium-term trend.
    if ema21 > ema50:
        score += 20
        reasons.append("medium trend positive")

    # Momentum.
    if 45 <= rsi <= 68:
        score += 15
        reasons.append(
            "momentum within preferred band"
        )

    # MACD confirmation.
    if macd > macd_signal:
        score += 15
        reasons.append("MACD positive")

    # Optional volume confirmation.
    volume = data.get("volume")
    volume_avg = data.get("volume_avg")

    if (
        valid_number(volume)
        and valid_number(volume_avg)
        and float(volume) >= 0
        and float(volume_avg) > 0
        and float(volume) >= float(volume_avg)
    ):
        score += 15
        reasons.append("volume above average")

    # Price position.
    if price > ema50:
        score += 15
        reasons.append("price above EMA50")

    return min(score, 100), reasons


# --------------------------------------------------
# Setup evaluation
# --------------------------------------------------

def evaluate_setup(
    frames,
    ai_vote="UNAVAILABLE",
    agreement=0.0,
    news_block=False
):
    """Evaluate a setup using deterministic multi-timeframe gates."""

    def hold(score, reason, details=None):

        if not valid_number(score):
            score = 0

        score = max(
            0.0,
            min(100.0, float(score))
        )

        result = {
            "action": "HOLD",
            "score": round(score, 2),
            "reason": str(reason),
        }

        if details is not None:
            result["timeframe_details"] = details

        return result

    # --------------------------------------------------
    # News safety gate
    # --------------------------------------------------

    if news_block:

        return hold(
            0,
            "news safety gate"
        )

    # --------------------------------------------------
    # Validate timeframe collection
    # --------------------------------------------------

    if not isinstance(frames, dict):

        return hold(
            0,
            "invalid timeframe collection"
        )

    missing = [
        timeframe
        for timeframe in TIMEFRAMES
        if timeframe not in frames
    ]

    if missing:

        return hold(
            0,
            "missing timeframe: " + ", ".join(missing)
        )

    # --------------------------------------------------
    # Validate and score all timeframes
    # --------------------------------------------------

    scores = {}
    details = {}

    for timeframe in TIMEFRAMES:

        data = frames[timeframe]

        validation_error = validate_timeframe(data)

        if validation_error:

            details[timeframe] = {
                "score": 0,
                "reasons": [validation_error],
            }

            return hold(
                0,
                f"invalid indicators: {timeframe}: "
                f"{validation_error}",
                details
            )

        score, reasons = score_timeframe(data)

        scores[timeframe] = score

        details[timeframe] = {
            "score": score,
            "reasons": reasons,
        }

    # --------------------------------------------------
    # Weighted multi-timeframe score
    # --------------------------------------------------

    weighted_score = (
        scores["15m"] * 0.50
        + scores["1h"] * 0.30
        + scores["4h"] * 0.20
    )

    # --------------------------------------------------
    # Higher timeframe alignment
    # --------------------------------------------------

    aligned = (
        float(frames["1h"]["ema9"])
        > float(frames["1h"]["ema21"])
        and
        float(frames["4h"]["ema9"])
        > float(frames["4h"]["ema21"])
    )

    score = weighted_score

    if aligned:
        score += 10

    # --------------------------------------------------
    # Validate AI agreement
    # --------------------------------------------------

    if isinstance(agreement, bool) or not valid_number(agreement):

        return hold(
            score,
            "invalid AI agreement value",
            details
        )

    agreement = float(agreement)

    if not 0 <= agreement <= 1:

        return hold(
            score,
            "AI agreement outside valid range",
            details
        )

    normalized_vote = (
        ai_vote.strip().upper()
        if isinstance(ai_vote, str)
        else "UNAVAILABLE"
    )

    # AI cannot override technical conditions.
    if (
        normalized_vote != "BUY"
        or agreement < config.AI_MIN_AGREEMENT
    ):

        return hold(
            score,
            "AI consensus unavailable or insufficient",
            details
        )

    # Small advisory bonus only.
    score += 5

    # --------------------------------------------------
    # Alignment gate
    # --------------------------------------------------

    if not aligned:

        return hold(
            score,
            "higher-timeframe conflict",
            details
        )

    # --------------------------------------------------
    # Entry threshold validation
    # --------------------------------------------------

    threshold = getattr(
        config,
        "MIN_SCORE_TO_ENTER",
        75.0
    )

    if not valid_number(threshold):

        return hold(
            score,
            "invalid entry threshold configuration",
            details
        )

    threshold = float(threshold)

    if not 0 <= threshold <= 100:

        return hold(
            score,
            "entry threshold outside valid range",
            details
        )

    score = min(
        100.0,
        score
    )

    if score < threshold:

        return hold(
            score,
            "score below threshold",
            details
        )

    # --------------------------------------------------
    # Paper entry candidate
    # --------------------------------------------------

    return {
        "action": "PAPER_BUY_CANDIDATE",
        "score": round(score, 2),
        "reason": (
            "quantitative and timeframe gates passed"
        ),
        "timeframe_details": details,
        "ai_agreement": round(agreement, 3),
    }

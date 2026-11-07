
"""Transparent deterministic scoring.
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


def valid_number(value):
    """Return True only for finite numeric values."""
    if isinstance(value, bool):
        return False

    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def score_timeframe(data):
    score = 0
    reasons = []

    if not isinstance(data, dict):
        return 0, ["invalid timeframe data"]

    for key in REQUIRED_INDICATORS:
        if not valid_number(data.get(key)):
            return 0, [f"invalid or missing indicator: {key}"]

    price = float(data["price"])
    ema9 = float(data["ema9"])
    ema21 = float(data["ema21"])
    ema50 = float(data["ema50"])
    rsi = float(data["rsi"])
    macd = float(data["macd"])
    macd_signal = float(data["macd_signal"])
    atr = float(data["atr"])

    if price <= 0 or atr <= 0:
        return 0, ["invalid price or ATR"]

    if not 0 <= rsi <= 100:
        return 0, ["RSI outside valid range"]

    if ema9 > ema21:
        score += 20
        reasons.append("short trend positive")

    if ema21 > ema50:
        score += 20
        reasons.append("medium trend positive")

    if 45 <= rsi <= 68:
        score += 15
        reasons.append("momentum within preferred band")

    if macd > macd_signal:
        score += 15
        reasons.append("MACD positive")

    volume = data.get("volume")
    volume_avg = data.get("volume_avg")

    if (
        valid_number(volume)
        and valid_number(volume_avg)
        and float(volume_avg) > 0
        and float(volume) >= float(volume_avg)
    ):
        score += 15
        reasons.append("volume above average")

    if price > ema50:
        score += 15
        reasons.append("price above EMA50")

    return min(score, 100), reasons


def evaluate_setup(
    frames,
    ai_vote="UNAVAILABLE",
    agreement=0.0,
    news_block=False
):
    """Evaluate a setup using deterministic multi-timeframe gates."""

    def hold(score, reason, details=None):
        result = {
            "action": "HOLD",
            "score": round(float(score), 2),
            "reason": reason,
        }

        if details is not None:
            result["timeframe_details"] = details

        return result

    # Safety gate: critical news blocks all candidate entries.
    if news_block:
        return hold(0, "news safety gate")

    if not isinstance(frames, dict):
        return hold(0, "invalid timeframe collection")

    if any(tf not in frames for tf in TIMEFRAMES):
        return hold(0, "missing timeframe")

    scores = {}
    details = {}

    for timeframe in TIMEFRAMES:
        score, reasons = score_timeframe(frames[timeframe])

        scores[timeframe] = score
        details[timeframe] = {
            "score": score,
            "reasons": reasons,
        }

        if score == 0:
            return hold(0, f"invalid indicators: {timeframe}", details)

    # Weighted deterministic score.
    weighted_score = (
        scores["15m"] * 0.50
        + scores["1h"] * 0.30
        + scores["4h"] * 0.20
    )

    # Higher timeframe alignment.
    aligned = (
        frames["1h"]["ema9"] > frames["1h"]["ema21"]
        and frames["4h"]["ema9"] > frames["4h"]["ema21"]
    )

    score = weighted_score + (10 if aligned else 0)

    # AI is advisory and cannot override quantitative gates.
    try:
        agreement = float(agreement)
    except (TypeError, ValueError, OverflowError):
        agreement = 0.0

    if not math.isfinite(agreement):
        agreement = 0.0

    agreement = max(0.0, min(1.0, agreement))

    if ai_vote != "BUY" or agreement < 0.60:
        return hold(
            score,
            "AI consensus unavailable or insufficient",
            details
        )

    score = min(100, score + 5)

    if not aligned:
        return hold(score, "higher-timeframe conflict", details)

    threshold = float(
        getattr(config, "MIN_SCORE_TO_ENTER", 75.0)
    )

    if score < threshold:
        return hold(score, "score below threshold", details)

    return {
        "action": "PAPER_BUY_CANDIDATE",
        "score": round(score, 2),
        "reason": "quantitative and timeframe gates passed",
        "timeframe_details": details,
        "ai_agreement": round(agreement, 3),
    }

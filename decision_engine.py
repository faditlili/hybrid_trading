from config import MIN_SCORE_TO_ENTER


def calculate_technical_score(indicators, market_regime):

    score = 0
    reasons = []

    if market_regime != "BULLISH":
        return {
            "score": 0,
            "reasons": ["Market regime is not bullish"]
        }

    required = [
        "price",
        "ema9",
        "ema21",
        "ema50",
        "rsi",
        "atr",
        "macd",
        "macd_signal",
        "volume",
        "volume_avg",
        "previous_close"
    ]

    if not isinstance(indicators, dict):
        return {"score": 0, "reasons": ["Invalid indicators"]}

    if any(
        key not in indicators
        for key in required
    ):
        return {"score": 0, "reasons": ["Missing indicators"]}

    try:
        values = {
            key: float(indicators[key])
            for key in required
        }
    except (TypeError, ValueError):
        return {"score": 0, "reasons": ["Invalid indicator values"]}

    import math

    if not all(math.isfinite(value) for value in values.values()):
        return {"score": 0, "reasons": ["Non-finite indicator values"]}

    if values["price"] <= 0 or values["atr"] <= 0:
        return {"score": 0, "reasons": ["Invalid price or ATR"]}

    if (
        values["ema9"] > values["ema21"]
        and values["ema21"] > values["ema50"]
    ):
        score += 25
        reasons.append("EMA bullish alignment")

    if values["price"] > values["ema50"]:
        score += 10
        reasons.append("Price above EMA50")

    if values["macd"] > values["macd_signal"]:
        score += 15
        reasons.append("MACD bullish")

    rsi = values["rsi"]

    if 48 <= rsi <= 68:
        score += 15
        reasons.append("RSI in preferred range")

    elif 42 <= rsi < 48 or 68 < rsi <= 72:
        score += 7
        reasons.append("RSI in acceptable range")

    if values["volume_avg"] > 0:

        volume_ratio = (
            values["volume"] / values["volume_avg"]
        )

        if volume_ratio >= 1.5:
            score += 10
            reasons.append("Strong volume")

        elif volume_ratio >= 1.0:
            score += 5
            reasons.append("Volume above average")

    if values["price"] > values["previous_close"]:
        score += 10
        reasons.append("Positive candle movement")

    return {
        "score": min(score, 85),
        "reasons": reasons
    }


def evaluate_setup(
    indicators,
    market_regime,
    ai_result
):

    technical = calculate_technical_score(
        indicators,
        market_regime
    )

    score = technical["score"]
    reasons = list(technical["reasons"])

    if market_regime != "BULLISH":
        return {
            "action": "WAIT",
            "score": 0,
            "reasons": reasons
        }

    if not isinstance(ai_result, dict):
        ai_result = {}

    vote = ai_result.get("vote", "UNAVAILABLE")

    if vote != "BUY":
        reasons.append("AI council did not confirm BUY")

        return {
            "action": "WAIT",
            "score": score,
            "reasons": reasons
        }

    score += 15
    reasons.append("AI council confirmation")

    action = (
        "PAPER_BUY"
        if score >= MIN_SCORE_TO_ENTER
        else "WAIT"
    )

    if action == "WAIT":
        reasons.append("Score below entry threshold")

    return {
        "action": action,
        "score": min(score, 100),
        "reasons": reasons
    }

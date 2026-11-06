import math
import logging

from config import MIN_SCORE_TO_ENTER


logger = logging.getLogger(__name__)


def valid_number(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def calculate_technical_score(indicators, market_regime):

    if not isinstance(indicators, dict):
        return {
            "score": 0,
            "reasons": ["Invalid indicators"],
            "valid": False
        }

    if market_regime not in (
        "BULLISH",
        "NOT_BULLISH",
        "UNKNOWN"
    ):
        market_regime = "UNKNOWN"

    if market_regime == "UNKNOWN":
        return {
            "score": 0,
            "reasons": ["BTC market regime is unknown"],
            "valid": False
        }

    required = [
        "price", "ema9", "ema21", "ema50",
        "rsi", "atr", "macd", "macd_signal",
        "volume", "volume_avg", "previous_close"
    ]

    for key in required:
        if key not in indicators or not valid_number(indicators[key]):
            return {
                "score": 0,
                "reasons": [f"Missing or invalid indicator: {key}"],
                "valid": False
            }

    values = {
        key: float(indicators[key])
        for key in required
    }

    if values["price"] <= 0 or values["atr"] <= 0:
        return {
            "score": 0,
            "reasons": ["Price or ATR is invalid"],
            "valid": False
        }

    if not 0 <= values["rsi"] <= 100:
        return {
            "score": 0,
            "reasons": ["RSI outside valid range"],
            "valid": False
        }

    if values["volume"] < 0 or values["volume_avg"] <= 0:
        return {
            "score": 0,
            "reasons": ["Invalid volume data"],
            "valid": False
        }

    score = 0
    reasons = []

    if values["ema9"] > values["ema21"] > values["ema50"]:
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
    else:
        reasons.append("RSI outside preferred range")

    volume_ratio = values["volume"] / values["volume_avg"]

    if volume_ratio >= 1.5:
        score += 10
        reasons.append("Strong volume")
    elif volume_ratio >= 1:
        score += 5
        reasons.append("Volume above average")
    else:
        reasons.append("Volume below average")

    if values["price"] > values["previous_close"]:
        score += 10
        reasons.append("Positive candle movement")
    else:
        reasons.append("No positive candle movement")

    # BTC is a risk factor, not a reason to stop scanning.
    if market_regime == "NOT_BULLISH":
        score = max(0, score - 10)
        reasons.append("BTC is not bullish: risk penalty applied")
    else:
        reasons.append("BTC market regime is bullish")

    return {
        "score": min(score, 85),
        "reasons": reasons,
        "valid": True
    }


def evaluate_setup(
    indicators,
    market_regime,
    ai_result,
    technical_result=None
):

    if technical_result is None:
        technical_result = calculate_technical_score(
            indicators,
            market_regime
        )

    if not isinstance(technical_result, dict):
        technical_result = {}

    if not technical_result.get("valid"):
        return {
            "action": "WAIT",
            "score": 0,
            "reasons": technical_result.get(
                "reasons",
                ["Technical analysis invalid"]
            ),
            "ai_vote": "UNAVAILABLE"
        }

    raw_score = technical_result.get("score", 0)

    if not valid_number(raw_score):
        return {
            "action": "WAIT",
            "score": 0,
            "reasons": ["Invalid technical score"],
            "ai_vote": "UNAVAILABLE"
        }

    technical_score = max(
        0,
        min(int(float(raw_score)), 85)
    )

    reasons = list(
        technical_result.get("reasons", [])
    )

    if not isinstance(ai_result, dict):
        ai_result = {}

    vote = str(
        ai_result.get("vote", "UNAVAILABLE")
    ).strip().upper()

    if vote not in ("BUY", "SELL", "HOLD", "UNAVAILABLE"):
        vote = "UNAVAILABLE"

    ai_reason = ai_result.get("reason", "")

    if ai_reason:
        reasons.append(f"AI: {str(ai_reason)[:200]}")

    if vote != "BUY":
        reasons.append(f"AI approval missing: {vote}")

        return {
            "action": "WAIT",
            "score": technical_score,
            "reasons": reasons,
            "ai_vote": vote
        }

    final_score = min(technical_score + 15, 100)

    reasons.append("AI BUY approval received")

    if final_score < MIN_SCORE_TO_ENTER:
        reasons.append(
            f"Score below threshold: {MIN_SCORE_TO_ENTER}"
        )

        return {
            "action": "WAIT",
            "score": final_score,
            "reasons": reasons,
            "ai_vote": vote
        }

    reasons.append("Entry conditions satisfied")

    return {
        "action": "PAPER_BUY",
        "score": final_score,
        "reasons": reasons,
        "ai_vote": vote
    }

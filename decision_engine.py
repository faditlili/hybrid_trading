import math
import logging

from config import MIN_SCORE_TO_ENTER


logger = logging.getLogger(__name__)


MAX_TECHNICAL_SCORE = 85
AI_APPROVAL_BONUS = 15

VALID_MARKET_REGIMES = {
    "BULLISH",
    "NOT_BULLISH",
    "UNKNOWN"
}

VALID_AI_VOTES = {
    "BUY",
    "SELL",
    "HOLD",
    "UNAVAILABLE"
}


def valid_number(value):

    if isinstance(value, bool):
        return False

    try:

        return math.isfinite(float(value))

    except (
        TypeError,
        ValueError,
        OverflowError
    ):

        return False


def valid_reasons(value):

    if not isinstance(value, (list, tuple)):
        return []

    return [
        str(reason)[:200]
        for reason in value
        if isinstance(reason, str) and reason.strip()
    ]


def calculate_technical_score(
    indicators,
    market_regime
):

    if not isinstance(indicators, dict):

        return {
            "score": 0,
            "reasons": ["Invalid indicators"],
            "valid": False
        }

    if not isinstance(market_regime, str):

        market_regime = "UNKNOWN"

    market_regime = market_regime.strip().upper()

    if market_regime not in VALID_MARKET_REGIMES:

        market_regime = "UNKNOWN"

    if market_regime == "UNKNOWN":

        return {
            "score": 0,
            "reasons": [
                "BTC market regime is unknown"
            ],
            "valid": False
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

    for key in required:

        if (
            key not in indicators
            or not valid_number(indicators[key])
        ):

            return {
                "score": 0,
                "reasons": [
                    f"Missing or invalid indicator: {key}"
                ],
                "valid": False
            }

    values = {
        key: float(indicators[key])
        for key in required
    }

    price = values["price"]
    ema9 = values["ema9"]
    ema21 = values["ema21"]
    ema50 = values["ema50"]
    rsi = values["rsi"]
    atr = values["atr"]
    macd = values["macd"]
    macd_signal = values["macd_signal"]
    volume = values["volume"]
    volume_avg = values["volume_avg"]
    previous_close = values["previous_close"]

    if (
        price <= 0
        or ema9 <= 0
        or ema21 <= 0
        or ema50 <= 0
        or previous_close <= 0
        or atr <= 0
    ):

        return {
            "score": 0,
            "reasons": [
                "Invalid price, EMA, ATR or previous close"
            ],
            "valid": False
        }

    if not 0 <= rsi <= 100:

        return {
            "score": 0,
            "reasons": [
                "RSI outside valid range"
            ],
            "valid": False
        }

    if volume < 0 or volume_avg <= 0:

        return {
            "score": 0,
            "reasons": [
                "Invalid volume data"
            ],
            "valid": False
        }

    score = 0
    reasons = []

    # EMA alignment.

    if ema9 > ema21 > ema50:

        score += 25

        reasons.append(
            "EMA bullish alignment"
        )

    # Price position.

    if price > ema50:

        score += 10

        reasons.append(
            "Price above EMA50"
        )

    # MACD momentum.

    if macd > macd_signal:

        score += 15

        reasons.append(
            "MACD bullish"
        )

    # RSI conditions.

    if 48 <= rsi <= 68:

        score += 15

        reasons.append(
            "RSI in preferred range"
        )

    elif 42 <= rsi < 48 or 68 < rsi <= 72:

        score += 7

        reasons.append(
            "RSI in acceptable range"
        )

    else:

        reasons.append(
            "RSI outside preferred range"
        )

    # Volume conditions.

    volume_ratio = volume / volume_avg

    if volume_ratio >= 1.5:

        score += 10

        reasons.append(
            "Strong volume"
        )

    elif volume_ratio >= 1:

        score += 5

        reasons.append(
            "Volume above average"
        )

    else:

        reasons.append(
            "Volume below average"
        )

    # Previous candle movement.

    if price > previous_close:

        score += 10

        reasons.append(
            "Positive candle movement"
        )

    else:

        reasons.append(
            "No positive candle movement"
        )

    # BTC market regime penalty.

    if market_regime == "NOT_BULLISH":

        score = max(
            0,
            score - 10
        )

        reasons.append(
            "BTC is not bullish: risk penalty applied"
        )

    else:

        reasons.append(
            "BTC market regime is bullish"
        )

    score = max(
        0,
        min(score, MAX_TECHNICAL_SCORE)
    )

    return {
        "score": score,
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

    if technical_result.get("valid") is not True:

        return {
            "action": "WAIT",
            "score": 0,
            "reasons": valid_reasons(
                technical_result.get(
                    "reasons",
                    ["Technical analysis invalid"]
                )
            ) or ["Technical analysis invalid"],
            "ai_vote": "UNAVAILABLE"
        }

    raw_score = technical_result.get(
        "score"
    )

    if not valid_number(raw_score):

        return {
            "action": "WAIT",
            "score": 0,
            "reasons": [
                "Invalid technical score"
            ],
            "ai_vote": "UNAVAILABLE"
        }

    raw_score = float(raw_score)

    if not 0 <= raw_score <= MAX_TECHNICAL_SCORE:

        return {
            "action": "WAIT",
            "score": 0,
            "reasons": [
                "Technical score outside valid range"
            ],
            "ai_vote": "UNAVAILABLE"
        }

    technical_score = int(raw_score)

    reasons = valid_reasons(
        technical_result.get("reasons", [])
    )

    if not isinstance(ai_result, dict):
        ai_result = {}

    raw_vote = ai_result.get(
        "vote",
        "UNAVAILABLE"
    )

    if not isinstance(raw_vote, str):

        vote = "UNAVAILABLE"

    else:

        vote = raw_vote.strip().upper()

    if vote not in VALID_AI_VOTES:

        vote = "UNAVAILABLE"

    ai_reason = ai_result.get(
        "reason",
        ""
    )

    if isinstance(ai_reason, str) and ai_reason.strip():

        reasons.append(
            f"AI: {ai_reason[:200]}"
        )

    # AI must explicitly approve the setup.

    if vote != "BUY":

        reasons.append(
            f"AI approval missing: {vote}"
        )

        return {
            "action": "WAIT",
            "score": technical_score,
            "reasons": reasons,
            "ai_vote": vote
        }

    # Apply a bounded AI approval bonus.

    final_score = min(
        technical_score + AI_APPROVAL_BONUS,
        100
    )

    reasons.append(
        "AI BUY approval received"
    )

    # Validate configured threshold.

    if not valid_number(MIN_SCORE_TO_ENTER):

        logger.error(
            "Invalid MIN_SCORE_TO_ENTER configuration"
        )

        return {
            "action": "WAIT",
            "score": technical_score,
            "reasons": reasons + [
                "Invalid entry threshold configuration"
            ],
            "ai_vote": vote
        }

    threshold = float(
        MIN_SCORE_TO_ENTER
    )

    if not 0 <= threshold <= 100:

        return {
            "action": "WAIT",
            "score": technical_score,
            "reasons": reasons + [
                "Entry threshold outside valid range"
            ],
            "ai_vote": vote
        }

    if final_score < threshold:

        reasons.append(
            f"Score below threshold: {threshold}"
        )

        return {
            "action": "WAIT",
            "score": final_score,
            "reasons": reasons,
            "ai_vote": vote
        }

    reasons.append(
        "Paper trading entry conditions satisfied"
    )

    return {
        "action": "PAPER_BUY",
        "score": final_score,
        "reasons": reasons,
        "ai_vote": vote
    }

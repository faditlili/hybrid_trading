import math
import logging

from config import MIN_SCORE_TO_ENTER


logger = logging.getLogger(__name__)


# ============================================================
# SCORING CONFIGURATION
# ============================================================

MAX_TECHNICAL_SCORE = 85
AI_APPROVAL_BONUS = 15

MAX_FINAL_SCORE = (
    MAX_TECHNICAL_SCORE + AI_APPROVAL_BONUS
)

VALID_MARKET_REGIMES = {
    "BULLISH",
    "NOT_BULLISH",
    "UNKNOWN",
}

VALID_AI_VOTES = {
    "BUY",
    "SELL",
    "HOLD",
    "UNAVAILABLE",
}


# ============================================================
# VALIDATION HELPERS
# ============================================================

def valid_number(value):

    if isinstance(value, bool):
        return False

    try:

        return math.isfinite(
            float(value)
        )

    except (
        TypeError,
        ValueError,
        OverflowError
    ):

        return False


def valid_reasons(value):

    if not isinstance(value, (list, tuple)):
        return []

    reasons = []

    for reason in value:

        if isinstance(reason, str) and reason.strip():

            reasons.append(
                reason.strip()[:200]
            )

        if len(reasons) >= 30:
            break

    return reasons


def invalid_result(reason):

    return {
        "score": 0,
        "reasons": [
            str(reason)[:200]
        ],
        "valid": False,
    }


def normalize_market_regime(market_regime):

    if not isinstance(market_regime, str):
        return "UNKNOWN"

    market_regime = (
        market_regime.strip().upper()
    )

    if market_regime not in VALID_MARKET_REGIMES:
        return "UNKNOWN"

    return market_regime


def normalize_ai_vote(value):

    if not isinstance(value, str):
        return "UNAVAILABLE"

    vote = value.strip().upper()

    if vote not in VALID_AI_VOTES:
        return "UNAVAILABLE"

    return vote


def validate_threshold():

    if not valid_number(MIN_SCORE_TO_ENTER):

        logger.error(
            "Invalid MIN_SCORE_TO_ENTER configuration"
        )

        return None

    threshold = float(
        MIN_SCORE_TO_ENTER
    )

    if not 0 <= threshold <= MAX_FINAL_SCORE:

        logger.error(
            "MIN_SCORE_TO_ENTER outside valid range"
        )

        return None

    return threshold


# ============================================================
# TECHNICAL SCORING
# ============================================================

def calculate_technical_score(
    indicators,
    market_regime
):

    if not isinstance(indicators, dict):

        return invalid_result(
            "Invalid indicators"
        )

    market_regime = normalize_market_regime(
        market_regime
    )

    if market_regime == "UNKNOWN":

        return invalid_result(
            "BTC market regime is unknown"
        )

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
        "previous_close",
    ]

    values = {}

    for key in required:

        if (
            key not in indicators
            or not valid_number(indicators[key])
        ):

            return invalid_result(
                f"Missing or invalid indicator: {key}"
            )

        values[key] = float(
            indicators[key]
        )

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

    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

    if (
        price <= 0
        or ema9 <= 0
        or ema21 <= 0
        or ema50 <= 0
        or previous_close <= 0
        or atr <= 0
    ):

        return invalid_result(
            "Invalid price, EMA, ATR or previous close"
        )

    if not 0 <= rsi <= 100:

        return invalid_result(
            "RSI outside valid range"
        )

    if volume < 0 or volume_avg <= 0:

        return invalid_result(
            "Invalid volume data"
        )

    volume_ratio = volume / volume_avg

    if not valid_number(volume_ratio):

        return invalid_result(
            "Invalid volume ratio"
        )

    # --------------------------------------------------------
    # SCORE CALCULATION
    # --------------------------------------------------------

    score = 0
    reasons = []

    # EMA alignment: 25 points

    if ema9 > ema21 > ema50:

        score += 25

        reasons.append(
            "EMA bullish alignment"
        )

    # Price position: 10 points

    if price > ema50:

        score += 10

        reasons.append(
            "Price above EMA50"
        )

    # MACD momentum: 15 points

    if macd > macd_signal:

        score += 15

        reasons.append(
            "MACD bullish"
        )

    # RSI: maximum 15 points

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

    # Volume: maximum 10 points

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

    # Previous candle movement: 10 points

    if price > previous_close:

        score += 10

        reasons.append(
            "Positive candle movement"
        )

    else:

        reasons.append(
            "No positive candle movement"
        )

    # --------------------------------------------------------
    # MARKET REGIME
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # FINAL TECHNICAL SCORE
    # --------------------------------------------------------

    score = max(
        0,
        min(
            score,
            MAX_TECHNICAL_SCORE
        )
    )

    return {

        "score": score,

        "reasons": reasons,

        "valid": True,

    }


# ============================================================
# TECHNICAL RESULT VALIDATION
# ============================================================

def validate_technical_result(
    technical_result,
    calculated_result
):

    if not isinstance(technical_result, dict):

        return False

    if technical_result.get("valid") is not True:

        return False

    supplied_score = technical_result.get(
        "score"
    )

    calculated_score = calculated_result.get(
        "score"
    )

    if (
        not valid_number(supplied_score)
        or not valid_number(calculated_score)
    ):

        return False

    supplied_score = float(
        supplied_score
    )

    calculated_score = float(
        calculated_score
    )

    if not 0 <= supplied_score <= MAX_TECHNICAL_SCORE:

        return False

    # Both results must come from the same
    # indicators and scoring configuration.

    if supplied_score != calculated_score:

        return False

    return True


# ============================================================
# FINAL SETUP EVALUATION
# ============================================================

def evaluate_setup(
    indicators,
    market_regime,
    ai_result,
    technical_result=None,
):

    market_regime = normalize_market_regime(
        market_regime
    )

    if market_regime == "UNKNOWN":

        return {

            "action": "WAIT",

            "score": 0,

            "reasons": [
                "BTC market regime is unknown"
            ],

            "ai_vote": "UNAVAILABLE",

        }

    # --------------------------------------------------------
    # RECALCULATE TECHNICAL RESULT
    # --------------------------------------------------------

    calculated_result = calculate_technical_score(
        indicators,
        market_regime
    )

    if calculated_result.get("valid") is not True:

        return {

            "action": "WAIT",

            "score": 0,

            "reasons": valid_reasons(
                calculated_result.get("reasons")
            ) or [
                "Technical analysis invalid"
            ],

            "ai_vote": "UNAVAILABLE",

        }

    # --------------------------------------------------------
    # VERIFY EXTERNAL TECHNICAL RESULT
    # --------------------------------------------------------

    if technical_result is not None:

        if not validate_technical_result(
            technical_result,
            calculated_result
        ):

            return {

                "action": "WAIT",

                "score": 0,

                "reasons": [
                    "Supplied technical result does not match indicators"
                ],

                "ai_vote": "UNAVAILABLE",

            }

    technical_score = float(
        calculated_result["score"]
    )

    reasons = valid_reasons(
        calculated_result.get("reasons", [])
    )

    # --------------------------------------------------------
    # AI RESULT VALIDATION
    # --------------------------------------------------------

    if not isinstance(ai_result, dict):
        ai_result = {}

    vote = normalize_ai_vote(
        ai_result.get(
            "vote",
            "UNAVAILABLE"
        )
    )

    ai_reason = ai_result.get(
        "reason",
        ""
    )

    if isinstance(ai_reason, str) and ai_reason.strip():

        reasons.append(
            f"AI: {ai_reason.strip()[:200]}"
        )

    # --------------------------------------------------------
    # AI MUST APPROVE
    # --------------------------------------------------------

    if vote != "BUY":

        reasons.append(
            f"AI approval missing: {vote}"
        )

        return {

            "action": "WAIT",

            "score": technical_score,

            "reasons": valid_reasons(reasons),

            "ai_vote": vote,

        }

    # --------------------------------------------------------
    # APPLY AI BONUS
    # --------------------------------------------------------

    final_score = min(
        technical_score + AI_APPROVAL_BONUS,
        MAX_FINAL_SCORE
    )

    reasons.append(
        "AI BUY approval received"
    )

    # --------------------------------------------------------
    # VALIDATE ENTRY THRESHOLD
    # --------------------------------------------------------

    threshold = validate_threshold()

    if threshold is None:

        reasons.append(
            "Invalid entry threshold configuration"
        )

        return {

            "action": "WAIT",

            "score": technical_score,

            "reasons": valid_reasons(reasons),

            "ai_vote": vote,

        }

    # --------------------------------------------------------
    # SCORE THRESHOLD
    # --------------------------------------------------------

    if final_score < threshold:

        reasons.append(
            f"Score below threshold: {threshold}"
        )

        return {

            "action": "WAIT",

            "score": final_score,

            "reasons": valid_reasons(reasons),

            "ai_vote": vote,

        }

    # --------------------------------------------------------
    # PAPER DECISION
    # --------------------------------------------------------

    reasons.append(
        "Paper trading entry conditions satisfied"
    )

    return {

        "action": "PAPER_BUY",

        "score": final_score,

        "reasons": valid_reasons(reasons),

        "ai_vote": vote,

    }

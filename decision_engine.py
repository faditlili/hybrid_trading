from config import MIN_SCORE_TO_ENTER


def evaluate_setup(indicators, market_regime, ai_result):
    score = 0
    reasons = []

    if market_regime != "BULLISH":
        return {
            "action": "WAIT",
            "score": 0,
            "reasons": ["السوق العام ليس صاعداً"]
        }

    if ai_result.get("vote") != "BUY":
        return {
            "action": "WAIT",
            "score": 0,
            "reasons": ["تصويت الذكاء الاصطناعي لا يؤكد الشراء"]
        }

    ema9 = indicators["ema9"]
    ema21 = indicators["ema21"]
    ema50 = indicators["ema50"]

    if ema9 > ema21 > ema50:
        score += 25
        reasons.append("ترتيب المتوسطات إيجابي")

    elif ema9 > ema21:
        score += 15
        reasons.append("تقاطع المتوسطات إيجابي جزئياً")

    if indicators["macd"] > indicators["macd_signal"]:
        score += 15
        reasons.append("MACD إيجابي")

    rsi = indicators["rsi"]

    if 48 <= rsi <= 68:
        score += 15
        reasons.append("RSI ضمن النطاق المحدد")

    volume = indicators["volume"]
    volume_avg = indicators["volume_avg"]

    if volume_avg > 0 and volume >= volume_avg * 1.2:
        score += 10
        reasons.append("حجم التداول أعلى من المتوسط")

    score += 15
    reasons.append("تصويت الذكاء الاصطناعي BUY")

    action = (
        "PAPER_BUY"
        if score >= MIN_SCORE_TO_ENTER
        else "WAIT"
    )

    if action == "WAIT":
        reasons.append("النقاط أقل من حد الدخول")

    return {
        "action": action,
        "score": score,
        "reasons": reasons
    }

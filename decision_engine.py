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
            "reasons": ["لا يوجد توافق كافٍ من نماذج الذكاء الاصطناعي"]
        }

    ema9 = indicators["ema9"]
    ema21 = indicators["ema21"]
    ema50 = indicators["ema50"]

    # اتجاه المتوسطات
    if ema9 > ema21 > ema50:
        score += 25
        reasons.append("ترتيب المتوسطات إيجابي بالكامل")

    elif ema9 > ema21:
        score += 15
        reasons.append("ترتيب المتوسطات إيجابي جزئياً")

    # موقع السعر بالنسبة للمتوسط الطويل
    if indicators["price"] > ema50:
        score += 10
        reasons.append("السعر أعلى EMA50")

    # MACD
    if indicators["macd"] > indicators["macd_signal"]:
        score += 15
        reasons.append("MACD إيجابي")

    # RSI
    rsi = indicators["rsi"]

    if 48 <= rsi <= 68:
        score += 15
        reasons.append("RSI ضمن النطاق المحدد")

    elif 42 <= rsi < 48 or 68 < rsi <= 72:
        score += 7
        reasons.append("RSI مقبول جزئياً")

    # حجم التداول
    volume = indicators["volume"]
    volume_avg = indicators["volume_avg"]

    if volume_avg > 0 and volume >= volume_avg * 1.2:
        score += 10
        reasons.append("حجم التداول أعلى من المتوسط")

    elif volume_avg > 0 and volume >= volume_avg:
        score += 5
        reasons.append("حجم التداول قريب من المتوسط")

    # حركة السعر الأخيرة
    if indicators["price"] > indicators["previous_close"]:
        score += 10
        reasons.append("إغلاق الشمعة أعلى من السابقة")

    # توافق الذكاء الاصطناعي
    score += 15
    reasons.append("توافق نماذج الذكاء الاصطناعي: BUY")

    action = (
        "PAPER_BUY"
        if score >= MIN_SCORE_TO_ENTER
        else "WAIT"
    )

    if action == "WAIT":
        reasons.append(
            f"النقاط {score} أقل من الحد المطلوب {MIN_SCORE_TO_ENTER}"
        )

    return {
        "action": action,
        "score": score,
        "reasons": reasons
    }

"""Transparent deterministic scoring. AI output is advisory and cannot bypass gates."""
def score_timeframe(x):
    score=0; reasons=[]
    if not x or any(x.get(k) is None for k in ("price","ema9","ema21","ema50","rsi","macd","macd_signal","atr")):
        return 0,["incomplete indicators"]
    if x["ema9"]>x["ema21"]: score+=20; reasons.append("short trend positive")
    if x["ema21"]>x["ema50"]: score+=20; reasons.append("medium trend positive")
    if 45<=x["rsi"]<=68: score+=15; reasons.append("momentum within preferred band")
    if x["macd"]>x["macd_signal"]: score+=15; reasons.append("MACD positive")
    if x.get("volume_avg") and x["volume"]>=x["volume_avg"]: score+=15; reasons.append("volume above average")
    if x["price"]>x["ema50"]: score+=15; reasons.append("price above EMA50")
    return min(score,100),reasons

def evaluate_setup(frames, ai_vote="UNAVAILABLE", agreement=0.0, news_block=False):
    if news_block: return {"action":"HOLD","score":0,"reason":"news safety gate"}
    if not all(k in frames for k in ("15m","1h","4h")): return {"action":"HOLD","score":0,"reason":"missing timeframe"}
    scores={k:score_timeframe(v)[0] for k,v in frames.items()}
    if any(v==0 for v in scores.values()): return {"action":"HOLD","score":0,"reason":"invalid indicators"}
    weighted=scores["15m"]*.5+scores["1h"]*.3+scores["4h"]*.2
    aligned=(frames["1h"]["ema9"]>frames["1h"]["ema21"] and frames["4h"]["ema9"]>frames["4h"]["ema21"])
    score=weighted+(10 if aligned else 0)
    if ai_vote!="BUY" or agreement<.6:
        return {"action":"HOLD","score":round(min(100,score),2),"reason":"AI consensus unavailable or insufficient"}
    score=min(100,score+5)
    if not aligned: return {"action":"HOLD","score":round(score,2),"reason":"higher-timeframe conflict"}
    if score<75: return {"action":"HOLD","score":round(score,2),"reason":"score below threshold"}
    return {"action":"PAPER_BUY_CANDIDATE","score":round(score,2),"reason":"quantitative and timeframe gates passed"}

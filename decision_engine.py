"""Conservative signal scoring engine matrix handles entries."""

def calculate_technical_score(ind):
    score = 0.0
    reasons = []
    # Evaluation gate for moving average crossovers
    e9 = ind.get("ema9")
    e21 = ind.get("ema21")
    e50 = ind.get("ema50")
    
    if e9 and e21 and e9 > e21:
        score += 20
        reasons.append("EMA9 above EMA21")
        
    if e21 and e50 and e21 > e50:
        score += 20
        reasons.append("EMA21 above EMA50")
    # Momentum and volatility matrix verification gates
    rsi_val = ind.get("rsi", 50)
    if 45 <= rsi_val <= 68:
        score += 15
        reasons.append(
            "RSI momentum in range"
        )
        
    if (
        ind.get("macd", 0) 
        > ind.get("macd_signal", 0)
    ):
        score += 15
        reasons.append(
            "MACD positive cross"
        )
    v_avg = ind.get("volume_avg", 0)
    if v_avg > 0 and ind.get("volume", 0) >= v_avg:
        score += 15
        reasons.append(
            "Volume above average"
        )
        
    return {
        "score": min(85, score), 
        "reasons": reasons
    }
def evaluate_setup(
    technical, ai_vote="UNAVAILABLE", 
    agreement=0.0, min_score=72, 
    min_agreement=.60
):
    score = float(technical.get("score", 0))
    zscore = float(technical.get("zscore", 0))
    
    if not 0 <= score <= 85:
        return {
            "action": "HOLD", "score": 0, 
            "reason": "Invalid score"
        }
    if zscore > 2.2:
        return {
            "action": "HOLD", "score": score, 
            "reason": "Z-Score veto limit"
        }
    if (
        ai_vote != "BUY" 
        or agreement < min_agreement 
        or score < min_score
    ):
        return {
            "action": "HOLD", "score": score, 
            "reason": "Consensus failed"
        }
        
    return {
        "action": "PAPER_BUY", 
        "score": score + 15, 
        "reason": "Signals synchronized"
    }

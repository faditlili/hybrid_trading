"""Deterministic backtester calculating commissions and slippage costs."""
import pandas as pd
def run_backtest(
    frame, fast=9, slow=21, 
    fee_rate=0.001, slippage_bps=5.0
):
    if fast < 2 or slow <= fast or fee_rate < 0: 
        raise ValueError(
            "Backtest configuration out of bounds."
        )
    d = frame.copy()
    d["close"] = pd.to_numeric(
        d["close"], errors="coerce"
    )
    d = d.dropna(subset=["close"])
    
    if len(d) < slow + 2: 
        raise ValueError(
            "Candle array context is insufficient."
        )
    d["f"] = (
        d.close.ewm(span=fast, adjust=False)
        .mean()
    )
    d["s"] = (
        d.close.ewm(span=slow, adjust=False)
        .mean()
    )
    
    signal = (
        (d.f > d.s).astype(int)
        .shift(1).fillna(0)
    )
    returns = d.close.pct_change().fillna(0)
    turnover = (
        signal.diff().abs()
        .fillna(signal)
    )
    cost_rate = fee_rate + (
        slippage_bps / 10000.0
    )
    strategy = (
        signal * returns 
        - turnover * cost_rate
    )
    equity = (1 + strategy).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak - 1).min()
    
    return {
        "candles": len(d), 
        "total_return_pct": float(
            (equity.iloc[-1] - 1) * 100
        ), 
        "max_drawdown_pct": float(
            drawdown * 100
        ), 
        "trades": int(turnover.sum())
    }

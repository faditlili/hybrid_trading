"""Small educational EMA crossover backtest; not a forecast or guarantee."""
import pandas as pd

def run_backtest(frame, fast=9, slow=21, fee_rate=0.001):
    if fast<2 or slow<=fast or not 0<=fee_rate<0.1: raise ValueError("Invalid backtest parameters")
    if "close" not in frame: raise ValueError("close column required")
    close=pd.to_numeric(frame.close,errors="coerce").dropna()
    if len(close)<slow+2: raise ValueError("Insufficient observations")
    a=close.ewm(span=fast,adjust=False).mean(); b=close.ewm(span=slow,adjust=False).mean()
    signal=(a>b).astype(int).shift(1).fillna(0); returns=close.pct_change().fillna(0)
    turnover=signal.diff().abs().fillna(signal); strategy=signal*returns-turnover*fee_rate
    curve=(1+strategy).cumprod(); peak=curve.cummax(); drawdown=curve/peak-1
    trades=int((turnover>0).sum()); wins=int((strategy>0).sum())
    return {"return_pct":float((curve.iloc[-1]-1)*100),"max_drawdown_pct":float(drawdown.min()*100),"observations":len(close),"turnovers":trades,"positive_period_pct":float(wins/max(1,len(strategy))*100)}

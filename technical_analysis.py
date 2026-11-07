"""Dependency-light OHLCV validation and indicator calculations."""
import math
import pandas as pd
import numpy as np

REQUIRED=("open","high","low","close","volume")

def validate_ohlcv(rows):
    frame = rows.copy() if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows, columns=REQUIRED)
    missing=[c for c in REQUIRED if c not in frame.columns]
    if missing: raise ValueError(f"Missing OHLCV columns: {missing}")
    frame=frame.loc[:,REQUIRED].apply(pd.to_numeric,errors="coerce").replace([np.inf,-np.inf],np.nan).dropna()
    frame=frame[(frame["open"]>0)&(frame["high"]>0)&(frame["low"]>0)&(frame["close"]>0)&(frame["volume"]>=0)]
    frame=frame[(frame.high>=frame[["open","close","low"]].max(axis=1))&(frame.low<=frame[["open","close","high"]].min(axis=1))]
    if len(frame)<60: raise ValueError("At least 60 valid candles are required")
    return frame.reset_index(drop=True)

def calculate_indicators(rows):
    f=validate_ohlcv(rows); c=f.close
    ema=lambda n: c.ewm(span=n,adjust=False,min_periods=n).mean()
    e9,e21,e50,e200=ema(9),ema(21),ema(50),ema(200)
    delta=c.diff(); gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False,min_periods=14).mean(); loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    rs=gain/loss.replace(0,np.nan); rsi=100-(100/(1+rs))
    fast=c.ewm(span=12,adjust=False).mean(); slow=c.ewm(span=26,adjust=False).mean(); macd=fast-slow; signal=macd.ewm(span=9,adjust=False).mean()
    prev=c.shift(1); tr=pd.concat([f.high-f.low,(f.high-prev).abs(),(f.low-prev).abs()],axis=1).max(axis=1); atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    volmean=f.volume.rolling(20).mean()
    def val(s):
        x=s.iloc[-1] if hasattr(s, "iloc") else s
        return float(x) if pd.notna(x) and math.isfinite(float(x)) else None
    return {"price":val(c),"ema9":val(e9),"ema21":val(e21),"ema50":val(e50),"ema200":val(e200),"rsi":val(rsi),"macd":val(macd),"macd_signal":val(signal),"atr":val(atr),"volume":val(f.volume),"volume_avg":val(volmean),"high_20":val(f.high.tail(20).max()),"low_20":val(f.low.tail(20).min()),"candles":len(f)}

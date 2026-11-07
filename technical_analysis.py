"""Low-latency indicators via pandas_ta bindings with Z-Score guards."""
import pandas as pd
import pandas_ta as ta

REQUIRED = (
    "open", "high", "low", 
    "close", "volume"
)
def validate_ohlcv(frame):
    if (
        not isinstance(frame, pd.DataFrame) 
        or not set(REQUIRED)
        .issubset(frame.columns)
    ): 
        raise ValueError(
            "Data columns are incomplete."
        )
        
    d = (
        frame.loc[:, REQUIRED]
        .apply(pd.to_numeric, errors="coerce")
        .dropna().copy()
    )
    if (
        len(d) < 60 
        or (d[["open", "high", "low", "close"]] <= 0)
        .any().any() 
        or (d.volume < 0).any()
    ): 
        raise ValueError(
            "Invalid values inside matrix."
        )
    return d
def calculate_indicators(frame):
    d = validate_ohlcv(frame)
    c = d["close"]
    out = {}
    # High-performance C-extensions EMA matrix loops
    for n in (9, 21, 50, 200):
        res = ta.ema(c, length=n)
        if (
            res is not None 
            and not res.empty 
            and pd.notna(res.iloc[-1])
        ):
            out[f"ema{n}"] = float(
                res.iloc[-1]
            )
        else:
            out[f"ema{n}"] = None
    rsi = ta.rsi(c, length=14)
    if rsi is not None and pd.notna(rsi.iloc[-1]):
        out["rsi"] = float(rsi.iloc[-1])
    else:
        out["rsi"] = 50.0
    macd_df = ta.macd(
        c, fast=12, slow=26, signal=9
    )
    if (
        macd_df is not None 
        and not macd_df.empty
    ):
        out["macd"] = float(
            macd_df.iloc[-1, 0]
        )
        out["macd_signal"] = float(
            macd_df.iloc[-1, 2]
        )
    else:
        out["macd"] = 0.0
        out["macd_signal"] = 0.0
    atr = ta.atr(
        d["high"], d["low"], c, length=14
    )
    if atr is not None and pd.notna(atr.iloc[-1]):
        out["atr"] = float(atr.iloc[-1])
    else:
        out["atr"] = 0.0
    zscore = ta.zscore(c, length=20)
    if (
        zscore is not None 
        and pd.notna(zscore.iloc[-1])
    ):
        out["zscore"] = float(
            zscore.iloc[-1]
        )
    else:
        out["zscore"] = 0.0
    out.update({
        "close": float(c.iloc[-1]), 
        "volume": float(d.volume.iloc[-1]), 
        "volume_avg": float(
            d.volume.tail(20).mean()
        ), 
        "candles": len(d)
    })
    # Market trend vector detection matrix
    e9 = out["ema9"] or 0
    e21 = out["ema21"] or 0
    e50 = out["ema50"] or 0
    
    if e9 > e21 > e50:
        out["trend"] = "BULLISH"
    elif e9 < e21 < e50:
        out["trend"] = "BEARISH"
    else:
        out["trend"] = "NEUTRAL"
        
    return out

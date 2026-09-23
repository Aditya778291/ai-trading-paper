from __future__ import annotations
import pandas as pd

def add_momentum_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    delta = result["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    # Preserve a meaningful RSI for strong one-sided moves. Replacing a
    # zero loss with NaN makes steadily rising series produce an all-NaN RSI.
    # When both average gain and loss are zero (flat prices), use the neutral
    # RSI value of 50.
    rs = avg_gain.div(avg_loss.where(avg_loss != 0))
    rsi = 100 - (100 / (1 + rs))
    rising = (avg_gain > 0) & (avg_loss == 0)
    flat = (avg_gain == 0) & (avg_loss == 0)
    rsi = rsi.mask(rising, 100.0).mask(flat, 50.0)
    result["RSI_14"] = rsi

    ema_fast = result["Close"].ewm(span=12, adjust=False).mean()
    ema_slow = result["Close"].ewm(span=26, adjust=False).mean()
    result["MACD"] = ema_fast - ema_slow
    result["MACD_SIGNAL"] = result["MACD"].ewm(span=9, adjust=False).mean()
    result["MACD_HIST"] = result["MACD"] - result["MACD_SIGNAL"]

    result["ROC_10"] = result["Close"].pct_change(10)
    result["MOMENTUM_10"] = result["Close"] - result["Close"].shift(10)
    return result

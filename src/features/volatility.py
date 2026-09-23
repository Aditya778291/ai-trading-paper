from __future__ import annotations
import pandas as pd

def add_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    prev_close = result["Close"].shift(1)
    true_range = pd.concat([
        result["High"] - result["Low"],
        (result["High"] - prev_close).abs(),
        (result["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    result["ATR_14"] = true_range.rolling(14).mean()

    mean = result["Close"].rolling(20).mean()
    std = result["Close"].rolling(20).std()
    result["BB_MIDDLE"] = mean
    result["BB_UPPER"] = mean + 2 * std
    result["BB_LOWER"] = mean - 2 * std
    result["BB_WIDTH"] = (result["BB_UPPER"] - result["BB_LOWER"]) / mean
    result["ROLLING_VOL_20"] = result["Close"].pct_change().rolling(20).std()
    return result

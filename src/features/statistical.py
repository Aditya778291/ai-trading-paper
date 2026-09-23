from __future__ import annotations
import numpy as np
import pandas as pd

def add_statistical_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["RETURN_1D"] = result["Close"].pct_change()
    result["LOG_RETURN_1D"] = np.log(result["Close"] / result["Close"].shift(1))

    for lag in (1, 2, 3, 5, 10):
        result[f"RETURN_LAG_{lag}"] = result["RETURN_1D"].shift(lag)
        result[f"CLOSE_LAG_{lag}"] = result["Close"].shift(lag)

    rolling_mean = result["Close"].rolling(20).mean()
    rolling_std = result["Close"].rolling(20).std()
    result["Z_SCORE_20"] = (result["Close"] - rolling_mean) / rolling_std
    result["HIGH_LOW_RANGE"] = (result["High"] - result["Low"]) / result["Close"]
    result["OPEN_CLOSE_CHANGE"] = (result["Close"] - result["Open"]) / result["Open"]
    result["DISTANCE_SMA_20"] = (result["Close"] / rolling_mean) - 1
    return result

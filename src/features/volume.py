from __future__ import annotations
import numpy as np
import pandas as pd

def add_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["VOLUME_SMA_20"] = result["Volume"].rolling(20).mean()
    result["RELATIVE_VOLUME"] = result["Volume"] / result["VOLUME_SMA_20"]
    result["VOLUME_CHANGE"] = result["Volume"].pct_change()

    direction = np.sign(result["Close"].diff()).fillna(0)
    result["OBV"] = (direction * result["Volume"]).cumsum()
    result["PRICE_VOLUME_TREND"] = (
        result["Close"].pct_change().fillna(0) * result["Volume"]
    ).cumsum()
    return result

from __future__ import annotations
import pandas as pd

def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for window in (10, 20, 50, 100, 200):
        result[f"SMA_{window}"] = result["Close"].rolling(window=window).mean()
    for span in (9, 21, 50):
        result[f"EMA_{span}"] = result["Close"].ewm(span=span, adjust=False).mean()
    return result

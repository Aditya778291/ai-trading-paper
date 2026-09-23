from __future__ import annotations
import pandas as pd

from src.features.technical import add_moving_averages
from src.features.momentum import add_momentum_features
from src.features.volatility import add_volatility_features
from src.features.volume import add_volume_features
from src.features.statistical import add_statistical_features

REQUIRED_COLUMNS = {"Open", "High", "Low", "Close", "Volume"}

def build_features(df: pd.DataFrame, drop_warmup_rows: bool = False) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas DataFrame")

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    result = df.copy().sort_index()

    # Every feature at timestamp t uses information available at or before t.
    result = add_moving_averages(result)
    result = add_momentum_features(result)
    result = add_volatility_features(result)
    result = add_volume_features(result)
    result = add_statistical_features(result)

    if drop_warmup_rows:
        result = result.dropna().copy()

    return result

import numpy as np
import pandas as pd

from src.features.feature_pipeline import build_features
from src.visualization.charts import (
    create_candlestick_chart,
    create_macd_chart,
    create_rsi_chart,
    create_volume_chart,
)


def make_data(rows: int = 250) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="B")
    close = np.linspace(100, 200, rows)
    return pd.DataFrame(
        {
            "Open": close - 1,
            "High": close + 2,
            "Low": close - 2,
            "Close": close,
            "Volume": np.arange(1000, 1000 + rows),
        },
        index=index,
    )


def test_chart_functions_return_figures():
    df = build_features(make_data())
    assert len(create_candlestick_chart(df).data) >= 1
    assert len(create_volume_chart(df).data) >= 1
    assert len(create_rsi_chart(df).data) >= 1
    assert len(create_macd_chart(df).data) >= 1

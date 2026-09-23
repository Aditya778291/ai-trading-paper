import numpy as np
import pandas as pd

from src.features.feature_pipeline import build_features

def make_data(rows: int = 250) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=rows, freq="B")
    close = pd.Series(np.linspace(100, 200, rows), index=idx)
    return pd.DataFrame({
        "Open": close - 1,
        "High": close + 2,
        "Low": close - 2,
        "Close": close,
        "Volume": np.arange(1000, 1000 + rows),
    }, index=idx)

def test_feature_pipeline_creates_expected_columns():
    result = build_features(make_data())
    expected = {
        "SMA_20", "EMA_21", "RSI_14", "MACD",
        "ATR_14", "BB_UPPER", "RELATIVE_VOLUME",
        "RETURN_1D", "Z_SCORE_20"
    }
    assert expected.issubset(result.columns)

def test_pipeline_can_drop_warmup_rows():
    result = build_features(make_data(), drop_warmup_rows=True)
    assert not result.empty
    assert result.isna().sum().sum() == 0

def test_pipeline_rejects_missing_columns():
    df = pd.DataFrame({"Close": [1, 2, 3]})
    try:
        build_features(df)
        assert False, "Expected ValueError"
    except ValueError:
        assert True

def test_rsi_handles_one_sided_price_series():
    result = build_features(make_data())
    assert result["RSI_14"].notna().any()
    assert result["RSI_14"].iloc[-1] == 100.0

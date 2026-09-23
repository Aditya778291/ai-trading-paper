import numpy as np
import pandas as pd

from src.features.scanner import scan_dataset, rank_momentum, rank_volume


def make_data(n=80):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 130, n), index=idx)
    return pd.DataFrame({
        "Open": close * 0.99,
        "High": close * 1.01,
        "Low": close * 0.98,
        "Close": close,
        "Volume": np.full(n, 1_000_000.0),
    }, index=idx)


def test_scan_dataset_returns_research_metrics():
    result = scan_dataset(make_data(), "TEST")
    assert result["Status"] == "OK"
    assert "RSI" in result
    assert "20D %" in result
    assert result["Above SMA50"] is True


def test_rankers_sort_descending():
    df = pd.DataFrame({"Symbol": ["A", "B"], "20D %": [1.0, 3.0], "Rel Volume": [1.1, 2.2]})
    assert rank_momentum(df).iloc[0]["Symbol"] == "B"
    assert rank_volume(df).iloc[0]["Symbol"] == "B"

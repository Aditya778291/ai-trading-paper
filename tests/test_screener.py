import numpy as np
import pandas as pd

from src.features.screener import Rule, prepare_features, apply_rules


def make_data(n=260):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 180, n), index=idx)
    return pd.DataFrame({
        "Open": close * .995,
        "High": close * 1.01,
        "Low": close * .99,
        "Close": close,
        "Volume": np.full(n, 1_000_000.0),
    }, index=idx)


def test_prepare_features_has_screening_fields():
    f = prepare_features(make_data())
    for col in ["__RET20_PCT", "__VOL20_PCT", "__SMA20_DIST", "__SMA50_DIST", "__SMA200_DIST"]:
        assert col in f.columns


def test_apply_rules_requires_all_conditions():
    f = prepare_features(make_data())
    row = f.iloc[-1]
    rules = [
        Rule("Close", ">", 100),
        Rule("SMA 50 Distance (%)", ">", 0),
    ]
    matched, _ = apply_rules(row, rules)
    assert matched is True

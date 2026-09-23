import numpy as np
import pandas as pd

from src.ai.intelligence import (
    classify_market_regime,
    ensemble_signal,
    explain_signal,
    model_health,
)


def test_ensemble_signal_is_transparent_and_bounded():
    results = pd.DataFrame({
        "Latest Probability": [0.70, 0.75, 0.65],
        "ROC AUC": [0.62, 0.61, 0.59],
        "Brier Score": [0.20, 0.21, 0.22],
        "Log Loss": [0.60, 0.62, 0.64],
    }, index=["A", "B", "C"])
    out = ensemble_signal(results)
    assert out["signal"] == "Bullish"
    assert 0 <= out["confidence"] <= 100
    assert out["agreement"] == 1.0


def test_regime_classification_returns_known_regime():
    idx = pd.date_range("2020-01-01", periods=80, freq="B")
    close = pd.Series(np.linspace(100, 150, len(idx)), index=idx)
    out = classify_market_regime(pd.DataFrame({"Close": close}))
    assert out["trend"] == "Bullish"
    assert "Bullish" in out["regime"]


def test_explanation_aggregates_models():
    a = pd.DataFrame({"Feature": ["RSI", "ATR"], "Importance": [0.8, 0.2]})
    b = pd.DataFrame({"Feature": ["RSI", "ATR"], "Importance": [0.6, 0.4]})
    out = explain_signal({"A": a, "B": b})
    assert out.iloc[0]["Feature"] == "RSI"
    assert out.iloc[0]["Models"] == 2


def test_model_health_flags_good_diagnostics():
    results = pd.DataFrame({
        "ROC AUC": [0.62],
        "Brier Score": [0.20],
        "Log Loss": [0.60],
        "Latest Probability": [0.7],
    }, index=["RF"])
    out = model_health(results)
    assert out.iloc[0]["Health"] == "Good"

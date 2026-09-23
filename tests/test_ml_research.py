import numpy as np
import pandas as pd

from src.models.ml_research import add_target, build_ml_dataset, chronological_split


def sample_df(n=260):
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    close = pd.Series(np.linspace(100, 140, n), index=idx)
    return pd.DataFrame({
        "Close": close,
        "RSI_14": np.linspace(40, 60, n),
        "ATR_14": np.ones(n),
        "RELATIVE_VOLUME": np.ones(n),
        "MACD": np.linspace(-1, 1, n),
        "MACD_SIGNAL": np.linspace(-0.8, 0.8, n),
        "MACD_HIST": np.zeros(n),
        "SMA_20": close.rolling(20).mean(),
        "SMA_50": close.rolling(50).mean(),
        "SMA_200": close.rolling(200).mean(),
        "EMA_12": close.ewm(span=12).mean(),
        "EMA_26": close.ewm(span=26).mean(),
    })


def test_target_uses_future_close_and_drops_tail_when_building():
    df = sample_df()
    labeled = add_target(df, horizon=5, threshold=0.0)
    assert labeled["TARGET"].iloc[-5:].isna().all()
    assert labeled["TARGET"].iloc[0] == 1


def test_chronological_split_preserves_order():
    data, _ = build_ml_dataset(sample_df(), horizon=5)
    train, test = chronological_split(data, 0.8)
    assert train.index.max() < test.index.min()


def test_dataset_has_no_missing_target_rows():
    data, features = build_ml_dataset(sample_df(), horizon=5)
    assert data["TARGET"].notna().all()
    assert features

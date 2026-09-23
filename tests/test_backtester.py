import numpy as np
import pandas as pd

from src.backtesting.backtester import (
    BacktestConfig,
    backtest_long_only,
    monte_carlo_summary,
    monte_carlo_trade_returns,
    walk_forward_slices,
)


def make_data():
    idx = pd.date_range("2024-01-01", periods=12, freq="D")
    close = np.array([100, 100, 102, 103, 104, 105, 106, 105, 104, 106, 107, 108], dtype=float)
    return pd.DataFrame({
        "Open": close,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": 1000,
    }, index=idx)


def test_next_bar_execution_avoids_lookahead():
    df = make_data()
    signal = pd.Series(False, index=df.index)
    signal.iloc[1] = True
    result = backtest_long_only(df, signal, BacktestConfig(commission_bps=0, slippage_bps=0))
    assert not result.trades.empty
    assert result.trades.iloc[0]["Entry Date"] == df.index[2]


def test_costs_reduce_return():
    df = make_data()
    signal = pd.Series(True, index=df.index)
    free = backtest_long_only(df, signal, BacktestConfig(commission_bps=0, slippage_bps=0))
    costly = backtest_long_only(df, signal, BacktestConfig(commission_bps=50, slippage_bps=50))
    assert costly.metrics["Final Equity"] < free.metrics["Final Equity"]


def test_stop_loss_exit():
    df = make_data()
    df.loc[df.index[3], "Low"] = 95
    signal = pd.Series(True, index=df.index)
    result = backtest_long_only(
        df, signal,
        BacktestConfig(commission_bps=0, slippage_bps=0, stop_loss_pct=0.03, take_profit_pct=None),
    )
    assert "Stop Loss" in set(result.trades["Reason"])


def test_drawdown_is_nonpositive():
    df = make_data()
    result = backtest_long_only(df, pd.Series(True, index=df.index))
    assert result.metrics["Max Drawdown"] <= 0


def test_walk_forward_slices_are_ordered():
    idx = pd.date_range("2020-01-01", periods=50, freq="D")
    slices = walk_forward_slices(idx, n_splits=4, min_train_bars=20)
    assert len(slices) == 4
    assert all(train[-1] < test[0] for train, test in slices)


def test_monte_carlo_shape_and_summary():
    trades = pd.DataFrame({"Net Return": [0.02, -0.01, 0.03, -0.02, 0.01]})
    sims = monte_carlo_trade_returns(trades, simulations=250, seed=7)
    summary = monte_carlo_summary(sims)
    assert len(sims) == 250
    assert 0 <= summary["Probability of Loss"] <= 1
    assert summary["Return P5"] <= summary["Return P95"]

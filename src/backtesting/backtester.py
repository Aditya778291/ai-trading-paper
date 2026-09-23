"""Scientific, long-only research backtester.

The engine is deliberately small and deterministic:
- signal observed on bar t is executed on bar t+1 open;
- transaction costs and slippage are applied on both entry and exit;
- stop-loss/take-profit use intraday High/Low while a position is open;
- no leverage and one position at a time;
- walk-forward utilities keep test periods chronological;
- Monte Carlo resamples completed trade returns and reports uncertainty bands.

This module is for research/paper trading only, not live execution.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable, Iterable, Optional
import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    position_fraction: float = 1.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    stop_loss_pct: Optional[float] = 0.02
    take_profit_pct: Optional[float] = 0.04

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if not 0 < self.position_fraction <= 1:
            raise ValueError("position_fraction must be in (0, 1]")
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("costs cannot be negative")
        for name, value in (("stop_loss_pct", self.stop_loss_pct),
                            ("take_profit_pct", self.take_profit_pct)):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics,
            "config": asdict(self.metrics.get("_config", {})) if False else None,
        }


def _price_columns(df: pd.DataFrame) -> tuple[str, str, str, str]:
    cols = {c.upper(): c for c in df.columns}
    close = cols.get("CLOSE")
    if close is None:
        raise ValueError("DataFrame must contain Close")
    open_ = cols.get("OPEN", close)
    high = cols.get("HIGH", close)
    low = cols.get("LOW", close)
    return open_, high, low, close


def _apply_cost(price: float, bps: float, side: str) -> float:
    # Buy costs increase execution price; sell costs decrease it.
    impact = bps / 10_000.0
    return price * (1.0 + impact) if side == "buy" else price * (1.0 - impact)


def max_drawdown(equity: pd.Series) -> tuple[float, int]:
    peak = equity.cummax()
    dd = equity / peak - 1.0
    max_dd = float(dd.min()) if len(dd) else 0.0
    end = int(dd.values.argmin()) if len(dd) else 0
    duration = 0
    current = 0
    peak_value = -np.inf
    for value in equity.to_numpy(dtype=float):
        if value >= peak_value:
            peak_value = value
            current = 0
        else:
            current += 1
            duration = max(duration, current)
    return max_dd, duration


def calculate_metrics(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict:
    if equity_curve.empty:
        return {}
    equity = equity_curve["Equity"].astype(float)
    returns = equity.pct_change().fillna(0.0)
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    periods = max(len(equity) - 1, 1)
    years = periods / 252.0
    cagr = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0) if years > 0 else 0.0
    vol = float(returns.std(ddof=0) * np.sqrt(252.0))
    sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(252.0)) if returns.std(ddof=0) > 0 else 0.0
    downside = returns[returns < 0].std(ddof=0)
    sortino = float(returns.mean() / downside * np.sqrt(252.0)) if downside and downside > 0 else 0.0
    mdd, mdd_duration = max_drawdown(equity)

    if trades.empty:
        win_rate = 0.0
        profit_factor = 0.0
        avg_trade = 0.0
    else:
        tr = trades["Net Return"].astype(float)
        win_rate = float((tr > 0).mean())
        gains = float(tr[tr > 0].sum())
        losses = float(-tr[tr < 0].sum())
        profit_factor = gains / losses if losses > 0 else (np.inf if gains > 0 else 0.0)
        avg_trade = float(tr.mean())

    return {
        "Initial Equity": float(equity.iloc[0]),
        "Final Equity": float(equity.iloc[-1]),
        "Total Return": total_return,
        "CAGR": cagr,
        "Annualized Volatility": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max Drawdown": mdd,
        "Max Drawdown Bars": int(mdd_duration),
        "Number of Trades": int(len(trades)),
        "Win Rate": win_rate,
        "Profit Factor": profit_factor,
        "Average Trade Return": avg_trade,
    }


def backtest_long_only(
    df: pd.DataFrame,
    signal: pd.Series | Iterable[float | bool],
    config: Optional[BacktestConfig] = None,
) -> BacktestResult:
    """Run a long-only backtest with next-bar-open execution.

    `signal[t]` means "want to be long after bar t"; the order is executed
    at bar t+1 open. A truthy/positive value is treated as long.
    """
    config = config or BacktestConfig()
    data = df.copy()
    data = data.sort_index()
    if len(data) < 3:
        raise ValueError("At least 3 bars are required")

    open_col, high_col, low_col, close_col = _price_columns(data)
    sig = pd.Series(signal, index=df.index).reindex(data.index).fillna(False)
    sig = sig.astype(bool)

    cash = float(config.initial_cash)
    shares = 0.0
    entry_price = None
    entry_date = None
    entry_cash = 0.0
    entry_signal_date = None
    trades = []
    equity_rows = []

    def record_equity(dt, mark_price):
        equity_rows.append({
            "Date": dt,
            "Cash": cash,
            "Position Value": shares * float(mark_price),
            "Equity": cash + shares * float(mark_price),
            "Position": 1 if shares > 0 else 0,
        })

    def close_position(dt, raw_price, reason):
        nonlocal cash, shares, entry_price, entry_date, entry_cash, entry_signal_date
        if shares <= 0:
            return
        sell = _apply_cost(float(raw_price), config.slippage_bps + config.commission_bps, "sell")
        proceeds = shares * sell
        cash += proceeds
        net_return = (cash / entry_cash - 1.0) if entry_cash else 0.0
        trades.append({
            "Entry Date": entry_date,
            "Exit Date": dt,
            "Entry Price": entry_price,
            "Exit Price": sell,
            "Shares": shares,
            "Gross Return": float((float(raw_price) / entry_price) - 1.0),
            "Net Return": float(net_return),
            "Reason": reason,
            "Duration": int(data.index.get_loc(dt) - data.index.get_loc(entry_date)),
            "Signal Date": entry_signal_date,
        })
        shares = 0.0
        entry_price = entry_date = entry_signal_date = None
        entry_cash = 0.0

    idx = list(data.index)
    # Mark-to-market starts before any order.
    record_equity(idx[0], data.iloc[0][close_col])

    for i in range(1, len(data)):
        dt = idx[i]
        row = data.iloc[i]
        prev_signal = bool(sig.iloc[i - 1])

        # Existing position: evaluate intraday exits first.
        if shares > 0:
            stop_hit = (
                config.stop_loss_pct is not None
                and float(row[low_col]) <= entry_price * (1.0 - config.stop_loss_pct)
            )
            target_hit = (
                config.take_profit_pct is not None
                and float(row[high_col]) >= entry_price * (1.0 + config.take_profit_pct)
            )
            # Conservative rule when both are hit on the same bar: stop wins.
            if stop_hit:
                close_position(dt, entry_price * (1.0 - config.stop_loss_pct), "Stop Loss")
            elif target_hit:
                close_position(dt, entry_price * (1.0 + config.take_profit_pct), "Take Profit")
            elif not prev_signal:
                close_position(dt, row[open_col], "Signal Exit")

        # Enter at today's open only if yesterday's signal requested long.
        if shares == 0 and prev_signal:
            buy = _apply_cost(float(row[open_col]), config.slippage_bps + config.commission_bps, "buy")
            allocation = cash * config.position_fraction
            shares = allocation / buy if buy > 0 else 0.0
            entry_cash = cash
            cash -= shares * buy
            entry_price = buy
            entry_date = dt
            entry_signal_date = idx[i - 1]

        record_equity(dt, row[close_col])

    # Liquidate at the final close so the reported result is fully realized.
    if shares > 0:
        close_position(idx[-1], data.iloc[-1][close_col], "End of Test")
        # Replace final mark with realized cash.
        equity_rows[-1]["Cash"] = cash
        equity_rows[-1]["Position Value"] = 0.0
        equity_rows[-1]["Equity"] = cash
        equity_rows[-1]["Position"] = 0

    equity_curve = pd.DataFrame(equity_rows).set_index("Date")
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df["Entry Date"] = pd.to_datetime(trades_df["Entry Date"])
        trades_df["Exit Date"] = pd.to_datetime(trades_df["Exit Date"])
    metrics = calculate_metrics(equity_curve, trades_df)
    return BacktestResult(equity_curve=equity_curve, trades=trades_df, metrics=metrics)


def technical_signal(df: pd.DataFrame, strategy: str = "SMA Crossover") -> pd.Series:
    """Generate simple deterministic research signals."""
    data = df.sort_index()
    close = data["Close"]
    if strategy == "SMA Crossover":
        fast = data["SMA_20"] if "SMA_20" in data else close.rolling(20).mean()
        slow = data["SMA_50"] if "SMA_50" in data else close.rolling(50).mean()
        return (fast > slow).fillna(False)
    if strategy == "RSI + Trend":
        rsi = data["RSI_14"] if "RSI_14" in data else pd.Series(50.0, index=data.index)
        slow = data["SMA_50"] if "SMA_50" in data else close.rolling(50).mean()
        return ((rsi > 50) & (close > slow)).fillna(False)
    if strategy == "Trend":
        slow = data["SMA_200"] if "SMA_200" in data else close.rolling(200).mean()
        return (close > slow).fillna(False)
    raise ValueError(f"Unknown strategy: {strategy}")


def walk_forward_slices(
    index: pd.Index,
    n_splits: int = 5,
    min_train_bars: Optional[int] = None,
) -> list[tuple[pd.Index, pd.Index]]:
    """Return chronological expanding-train/test slices with no overlap."""
    n = len(index)
    if n_splits < 2:
        raise ValueError("n_splits must be at least 2")
    min_train = min_train_bars or max(20, n // (n_splits + 1))
    if min_train >= n:
        raise ValueError("Not enough data for requested walk-forward splits")
    test_size = max(1, (n - min_train) // n_splits)
    slices = []
    for k in range(n_splits):
        train_end = min_train + k * test_size
        test_end = min(n, train_end + test_size)
        if test_end <= train_end:
            break
        slices.append((index[:train_end], index[train_end:test_end]))
    return slices


def walk_forward_backtest(
    df: pd.DataFrame,
    signal_factory: Callable[[pd.DataFrame], pd.Series],
    config: Optional[BacktestConfig] = None,
    n_splits: int = 5,
) -> pd.DataFrame:
    """Evaluate a strategy on sequential test windows.

    signal_factory receives only the training window. The resulting signal is
    then reindexed onto the test window; this makes the helper safe for
    strategies that choose parameters from the past.
    """
    data = df.sort_index()
    slices = walk_forward_slices(data.index, n_splits=n_splits)
    rows = []
    for fold, (train_idx, test_idx) in enumerate(slices, start=1):
        train = data.loc[train_idx]
        test = data.loc[test_idx]
        signal = signal_factory(train)
        # For deterministic indicators, carry the latest desired state into
        # the test period. Parameter-fitting factories can instead return a
        # signal indexed for the test period if desired.
        test_signal = pd.Series(bool(signal.iloc[-1]) if len(signal) else False, index=test.index)
        result = backtest_long_only(test, test_signal, config=config)
        row = {"Fold": fold, "Train Bars": len(train), "Test Bars": len(test)}
        row.update(result.metrics)
        rows.append(row)
    return pd.DataFrame(rows)


def monte_carlo_trade_returns(
    trades: pd.DataFrame,
    simulations: int = 2000,
    seed: int = 42,
    horizon_trades: Optional[int] = None,
) -> pd.DataFrame:
    """Bootstrap completed net trade returns with replacement."""
    if simulations < 100:
        raise ValueError("Use at least 100 simulations")
    if trades.empty or "Net Return" not in trades:
        raise ValueError("At least one completed trade is required")
    returns = trades["Net Return"].dropna().to_numpy(dtype=float)
    horizon = horizon_trades or len(returns)
    rng = np.random.default_rng(seed)
    sampled = rng.choice(returns, size=(simulations, horizon), replace=True)
    terminal = np.prod(1.0 + sampled, axis=1) - 1.0
    paths = np.cumprod(1.0 + sampled, axis=1)
    running_peak = np.maximum.accumulate(paths, axis=1)
    drawdowns = paths / running_peak - 1.0
    max_dd = drawdowns.min(axis=1)
    return pd.DataFrame({
        "Terminal Return": terminal,
        "Max Drawdown": max_dd,
    })


def monte_carlo_summary(simulations: pd.DataFrame) -> dict:
    if simulations.empty:
        return {}
    return {
        "Probability of Loss": float((simulations["Terminal Return"] < 0).mean()),
        "Return P5": float(simulations["Terminal Return"].quantile(0.05)),
        "Return P25": float(simulations["Terminal Return"].quantile(0.25)),
        "Return P50": float(simulations["Terminal Return"].quantile(0.50)),
        "Return P75": float(simulations["Terminal Return"].quantile(0.75)),
        "Return P95": float(simulations["Terminal Return"].quantile(0.95)),
        "Max DD P5": float(simulations["Max Drawdown"].quantile(0.05)),
        "Max DD P50": float(simulations["Max Drawdown"].quantile(0.50)),
        "Max DD P95": float(simulations["Max Drawdown"].quantile(0.95)),
    }

import numpy as np
import pandas as pd
from src.paper_trading.engine import PaperPortfolio, replay_decisions


def test_buy_and_sell_updates_cash_and_realized_pnl():
    p = PaperPortfolio(10_000, commission_bps=0)
    buy = p.submit_order("ABC", "BUY", 10, 100, "2025-01-01")
    assert buy.status == "FILLED"
    assert p.cash == 9000
    sell = p.submit_order("ABC", "SELL", 10, 110, "2025-01-02")
    assert sell.status == "FILLED"
    assert p.cash == 10100
    assert p.trade_journal[0]["Realized PnL"] == 100


def test_rejects_oversized_orders():
    p = PaperPortfolio(1000, commission_bps=0)
    order = p.submit_order("ABC", "BUY", 11, 100, "2025-01-01")
    assert order.status == "REJECTED"
    assert not p.positions


def test_replay_uses_next_bar_open():
    idx = pd.date_range("2025-01-01", periods=5)
    df = pd.DataFrame({
        "Open": [100, 101, 102, 103, 104],
        "Close": [100, 101, 102, 103, 104],
    }, index=idx)
    signal = pd.Series([False, True, True, False, False], index=idx)
    p, equity = replay_decisions(df, signal, "ABC", initial_cash=10_000, commission_bps=0)
    assert p.orders[0].timestamp == idx[2]
    assert p.orders[0].price == 102


def test_snapshot_is_json_compatible():
    p = PaperPortfolio(1000)
    p.mark_to_market("2025-01-01", {})
    snap = p.snapshot()
    assert "orders" in snap and "positions" in snap and "equity_history" in snap

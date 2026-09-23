"""Paper-trading portfolio and decision-replay engine.

No broker connectivity is implemented here. Orders are simulated against
historical bars and persisted only in memory / JSON-compatible dictionaries.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
import json
import pandas as pd


@dataclass
class Order:
    order_id: int
    timestamp: object
    symbol: str
    side: str
    quantity: float
    order_type: str = "MARKET"
    price: Optional[float] = None
    status: str = "FILLED"
    reason: str = ""
    signal: Optional[float] = None


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    market_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.market_price - self.avg_price)


class PaperPortfolio:
    def __init__(self, initial_cash: float = 100_000.0, commission_bps: float = 5.0):
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if commission_bps < 0:
            raise ValueError("commission_bps cannot be negative")
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.commission_bps = float(commission_bps)
        self.positions: dict[str, Position] = {}
        self.orders: list[Order] = []
        self.trade_journal: list[dict] = []
        self.equity_history: list[dict] = []
        self._next_order_id = 1

    def _cost(self, notional: float) -> float:
        return abs(notional) * self.commission_bps / 10_000.0

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        timestamp=None,
        reason: str = "",
        signal: Optional[float] = None,
    ) -> Order:
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity and price must be positive")

        notional = quantity * price
        cost = self._cost(notional)
        order = Order(
            self._next_order_id, timestamp, symbol, side, float(quantity),
            price=float(price), reason=reason, signal=signal
        )
        self._next_order_id += 1

        if side == "BUY":
            required = notional + cost
            if required > self.cash + 1e-9:
                order.status = "REJECTED"
                order.reason = reason or "Insufficient cash"
                self.orders.append(order)
                return order
            old = self.positions.get(symbol)
            if old:
                total_qty = old.quantity + quantity
                old.avg_price = ((old.quantity * old.avg_price) + notional + cost) / total_qty
                old.quantity = total_qty
                old.market_price = price
            else:
                self.positions[symbol] = Position(symbol, quantity, price + cost / quantity, price)
            self.cash -= required
        else:
            old = self.positions.get(symbol)
            if not old or quantity > old.quantity + 1e-9:
                order.status = "REJECTED"
                order.reason = reason or "Insufficient position"
                self.orders.append(order)
                return order
            proceeds = notional - cost
            realized = quantity * (price - old.avg_price) - cost
            self.cash += proceeds
            old.quantity -= quantity
            if old.quantity <= 1e-9:
                del self.positions[symbol]
            else:
                old.market_price = price
            self.trade_journal.append({
                "Order ID": order.order_id,
                "Timestamp": timestamp,
                "Symbol": symbol,
                "Side": "SELL",
                "Quantity": quantity,
                "Price": price,
                "Realized PnL": realized,
                "Reason": reason,
                "Signal": signal,
            })
        self.orders.append(order)
        return order

    def mark_to_market(self, timestamp, prices: dict[str, float]) -> dict:
        position_value = 0.0
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.market_price = float(prices[symbol])
            position_value += position.market_value
        row = {
            "Timestamp": timestamp,
            "Cash": self.cash,
            "Position Value": position_value,
            "Equity": self.cash + position_value,
        }
        self.equity_history.append(row)
        return row

    def snapshot(self) -> dict:
        return {
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "commission_bps": self.commission_bps,
            "positions": [asdict(p) for p in self.positions.values()],
            "orders": [asdict(o) for o in self.orders],
            "trade_journal": self.trade_journal,
            "equity_history": self.equity_history,
        }

    def save_snapshot(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.snapshot(), default=str, indent=2), encoding="utf-8")


def replay_decisions(
    df: pd.DataFrame,
    signal: pd.Series,
    symbol: str,
    initial_cash: float = 100_000.0,
    commission_bps: float = 5.0,
    position_fraction: float = 1.0,
) -> tuple[PaperPortfolio, pd.DataFrame]:
    """Replay a long-only signal chronologically using next-bar-open fills."""
    if "Open" not in df or "Close" not in df:
        raise ValueError("DataFrame must contain Open and Close")
    data = df.sort_index()
    sig = pd.Series(signal, index=df.index).reindex(data.index).fillna(False).astype(bool)
    portfolio = PaperPortfolio(initial_cash, commission_bps)

    for i in range(1, len(data)):
        row = data.iloc[i]
        prev = bool(sig.iloc[i - 1])
        position = portfolio.positions.get(symbol)

        if position and not prev:
            portfolio.submit_order(symbol, "SELL", position.quantity, float(row["Open"]),
                                   data.index[i], "Signal Exit", float(sig.iloc[i - 1]))
        elif not position and prev:
            allocation = portfolio.cash * position_fraction
            qty = allocation / float(row["Open"])
            portfolio.submit_order(symbol, "BUY", qty, float(row["Open"]),
                                   data.index[i], "Signal Entry", float(sig.iloc[i - 1]))

        portfolio.mark_to_market(data.index[i], {symbol: float(row["Close"])})

    if symbol in portfolio.positions:
        p = portfolio.positions[symbol]
        portfolio.submit_order(symbol, "SELL", p.quantity, float(data.iloc[-1]["Close"]),
                                data.index[-1], "End of Replay")
        portfolio.mark_to_market(data.index[-1], {symbol: float(data.iloc[-1]["Close"])})

    return portfolio, pd.DataFrame(portfolio.equity_history).set_index("Timestamp")


def decision_replay_table(portfolio: PaperPortfolio) -> pd.DataFrame:
    """Return an audit-friendly order/journal table."""
    rows = []
    for order in portfolio.orders:
        rows.append({
            "Order ID": order.order_id,
            "Timestamp": order.timestamp,
            "Symbol": order.symbol,
            "Side": order.side,
            "Quantity": order.quantity,
            "Price": order.price,
            "Status": order.status,
            "Reason": order.reason,
            "Signal": order.signal,
        })
    return pd.DataFrame(rows)

from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Portfolio, Position
from .market_data import market_data, MarketDataError


def mark_portfolio_to_market(db: Session, portfolio: Portfolio, force: bool = False) -> dict:
    """Refresh open positions using current quotes and return an equity snapshot."""
    positions = list(db.scalars(select(Position).where(Position.portfolio_id == portfolio.id, Position.quantity != 0)).all())
    errors = []
    market_value = 0.0
    for pos in positions:
        try:
            pos.market_price = market_data.quote(pos.symbol, force=force).price
        except MarketDataError as exc:
            errors.append(str(exc))
        market_value += pos.quantity * pos.market_price
    db.commit()
    return {
        'cash': portfolio.cash,
        'market_value': market_value,
        'equity': portfolio.cash + market_value,
        'positions': [
            {
                'symbol': p.symbol, 'quantity': p.quantity, 'avg_price': p.avg_price,
                'market_price': p.market_price, 'market_value': p.quantity * p.market_price,
                'unrealized_pnl': (p.market_price - p.avg_price) * p.quantity,
            } for p in positions
        ],
        'quote_errors': errors,
    }

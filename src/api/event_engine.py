from __future__ import annotations
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import select
from .database import SessionLocal
from .models import Portfolio, Position, Order, Trade
from .market_data import market_data, MarketDataError
from .config import settings
from .notifications import notifier
from .audit import AuditEvent

log = logging.getLogger(__name__)

@dataclass
class EngineStats:
    cycles: int = 0
    quotes: int = 0
    exits: int = 0
    errors: int = 0
    last_cycle: datetime | None = None

class PaperTradingLoop:
    """Event-driven paper-trading monitor with automatic risk exits.

    Polls open positions, rejects stale quotes, updates mark-to-market prices,
    evaluates a lightweight short-term momentum signal, and automatically closes
    positions when stop-loss/take-profit levels are crossed. No broker execution.
    """
    def __init__(self, interval_seconds: float = 15.0, max_quote_age_seconds: float = 30.0):
        self.interval_seconds = max(0.25, float(interval_seconds))
        self.max_quote_age_seconds = max(1.0, float(max_quote_age_seconds))
        self.stats = EngineStats()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._previous_prices: dict[str, float] = {}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if self.running:
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='paper-trading-loop', daemon=True)
        self._thread.start()
        return True

    def stop(self) -> bool:
        if not self.running:
            return False
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval_seconds + 1.0))
        return True

    def _signal(self, symbol: str, price: float) -> dict:
        previous = self._previous_prices.get(symbol)
        self._previous_prices[symbol] = price
        if previous is None or previous <= 0:
            return {'signal': 'HOLD', 'confidence': 0.0, 'return_pct': 0.0}
        ret = (price / previous - 1.0) * 100.0
        signal = 'BUY' if ret > 0.25 else 'SELL' if ret < -0.25 else 'HOLD'
        confidence = min(100.0, abs(ret) * 100.0) if signal != 'HOLD' else 0.0
        return {'signal': signal, 'confidence': round(confidence, 2), 'return_pct': round(ret, 4)}

    def _execute_risk_exit(self, db, pos: Position, price: float, reason: str) -> dict:
        quantity = pos.quantity
        gross = quantity * price
        fee = gross * settings.commission_bps / 10000.0
        realized = (price - pos.avg_price) * quantity - fee
        portfolio = db.get(Portfolio, pos.portfolio_id)
        portfolio.cash += gross - fee
        pos.quantity = 0
        pos.avg_price = 0
        pos.market_price = price
        pos.stop_loss = None
        pos.take_profit = None
        o = Order(portfolio_id=portfolio.id, symbol=pos.symbol, side='SELL', quantity=quantity,
                  price=price, status='FILLED', reason=reason, signal='RISK_EXIT',
                  idempotency_key=f'risk-exit-{portfolio.id}-{pos.symbol}-{reason}-{self.stats.cycles}')
        db.add(o); db.flush()
        db.add(Trade(portfolio_id=portfolio.id, order_id=o.id, symbol=pos.symbol, side='SELL',
                     quantity=quantity, price=price, realized_pnl=realized, reason=reason, signal='RISK_EXIT'))
        db.add(AuditEvent(user_id=portfolio.user_id, event='risk.exit', detail=f'{{"symbol":"{pos.symbol}","reason":"{reason}","price":{price}}}'))
        notifier.notify('risk.exit', {'order_id': o.id, 'symbol': pos.symbol, 'quantity': quantity, 'price': price, 'reason': reason})
        return {'order_id': o.id, 'symbol': pos.symbol, 'quantity': quantity, 'price': price, 'reason': reason, 'realized_pnl': realized}

    def run_once(self) -> dict:
        db = SessionLocal()
        try:
            portfolios = list(db.scalars(select(Portfolio)).all())
            positions = list(db.scalars(select(Position).where(Position.quantity != 0)).all())
            quote_count = 0
            stale = []
            exits = []
            signals = []
            for pos in positions:
                try:
                    q = market_data.quote(pos.symbol, force=True)
                    age = max(0.0, (datetime.now(timezone.utc) - q.timestamp).total_seconds())
                    if age > self.max_quote_age_seconds:
                        stale.append({'symbol': pos.symbol, 'age_seconds': round(age, 2)})
                        continue
                    pos.market_price = q.price
                    quote_count += 1
                    sig = self._signal(pos.symbol, q.price)
                    signals.append({'symbol': pos.symbol, **sig})
                    reason = None
                    if pos.stop_loss is not None and q.price <= pos.stop_loss:
                        reason = 'stop-loss'
                    elif pos.take_profit is not None and q.price >= pos.take_profit:
                        reason = 'take-profit'
                    if reason:
                        exits.append(self._execute_risk_exit(db, pos, q.price, reason))
                except MarketDataError as exc:
                    self.stats.errors += 1
                    log.warning('quote refresh failed symbol=%s error=%s', pos.symbol, exc)
            db.commit()
            self.stats.cycles += 1
            self.stats.quotes += quote_count
            self.stats.exits += len(exits)
            self.stats.last_cycle = datetime.now(timezone.utc)
            return {'portfolios': len(portfolios), 'positions': len(positions), 'quotes': quote_count,
                    'triggers': exits, 'signals': signals, 'stale_quotes': stale,
                    'timestamp': self.stats.last_cycle}
        finally:
            db.close()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                self.stats.errors += 1
                log.exception('paper trading loop cycle failed')
            self._stop.wait(self.interval_seconds)

engine = PaperTradingLoop()

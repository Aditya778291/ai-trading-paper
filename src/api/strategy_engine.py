from __future__ import annotations
from dataclasses import dataclass
import threading
from datetime import datetime, timezone
from sqlalchemy import select
from .database import SessionLocal
from .models import Portfolio, Position, Strategy
from .market_data import market_data, MarketDataError
from .config import settings
from .notifications import notifier
from .event_engine import engine

@dataclass
class StrategyStats:
    cycles: int = 0
    signals: int = 0
    orders: int = 0
    rejected: int = 0
    errors: int = 0
    last_cycle: datetime | None = None

class StrategyEngine:
    """Automated paper strategy runner. Never sends orders to a broker."""
    def __init__(self, interval_seconds: float = 30.0):
        self.stats = StrategyStats()
        self.interval_seconds = max(1.0, float(interval_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_action: dict[tuple[int, str], float] = {}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if self.running: return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='strategy-engine', daemon=True)
        self._thread.start()
        return True

    def stop(self) -> bool:
        if not self.running: return False
        self._stop.set()
        self._thread.join(timeout=max(1.0, self.interval_seconds + 1.0))
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            try: self.run_once()
            except Exception: self.stats.errors += 1
            self._stop.wait(self.interval_seconds)

    def _signal(self, symbol: str, price: float) -> tuple[str, float]:
        # Share the same price history used by the paper-trading event loop.
        # This keeps strategy signals deterministic and prevents two independent
        # previous-price stores from producing inconsistent BUY/SELL decisions.
        previous = engine._previous_prices.get(symbol)
        engine._previous_prices[symbol] = price
        if previous is None or previous <= 0:
            return 'HOLD', 0.0
        ret = (price / previous - 1.0) * 100.0
        signal = 'BUY' if ret > 0.25 else 'SELL' if ret < -0.25 else 'HOLD'
        confidence = min(100.0, abs(ret) * 100.0) if signal != 'HOLD' else 0.0
        return signal, round(confidence, 2)

    def _eligible(self, db, strategy: Strategy, portfolio: Portfolio, symbol: str, signal: str, confidence: float, price: float) -> tuple[bool, str]:
        if not strategy.enabled: return False, 'strategy-disabled'
        if signal == 'HOLD' or confidence < strategy.min_confidence: return False, 'signal-below-threshold'
        key=(strategy.id, symbol); now=datetime.now(timezone.utc).timestamp()
        if now - self._last_action.get(key, 0) < strategy.cooldown_seconds: return False, 'cooldown'
        pos=db.scalar(select(Position).where(Position.portfolio_id==portfolio.id, Position.symbol==symbol))
        open_positions=list(db.scalars(select(Position).where(Position.portfolio_id==portfolio.id, Position.quantity!=0)).all())
        if signal == 'BUY':
            if pos and pos.quantity > 0: return False, 'already-long'
            if len(open_positions) >= strategy.max_open_positions: return False, 'max-open-positions'
            equity=portfolio.cash + sum(x.quantity*x.market_price for x in open_positions)
            current_exposure=sum(max(0.0,x.quantity*x.market_price) for x in open_positions)
            max_exposure=equity*strategy.max_exposure_pct/100.0
            budget=min(equity*strategy.position_size_pct/100.0, max(0.0,max_exposure-current_exposure))
            if budget < price: return False, 'position-budget-too-small'
        else:
            if not pos or pos.quantity <= 0: return False, 'no-long-position'
        return True, 'ok'

    def _buy_quantity(self, strategy: Strategy, portfolio: Portfolio, price: float, db=None) -> float:
        open_positions=[] if db is None else list(db.scalars(select(Position).where(Position.portfolio_id==portfolio.id, Position.quantity!=0)).all())
        equity=portfolio.cash + sum(x.quantity*x.market_price for x in open_positions)
        current_exposure=sum(max(0.0,x.quantity*x.market_price) for x in open_positions)
        budget=min(equity*strategy.position_size_pct/100.0, max(0.0,equity*strategy.max_exposure_pct/100.0-current_exposure))
        return max(0.0, min(budget, portfolio.cash) / price)

    def run_once(self) -> dict:
        db=SessionLocal(); actions=[]; signals=[]; errors=[]
        try:
            strategies=list(db.scalars(select(Strategy).where(Strategy.enabled == True)).all())
            # Fetch and classify each symbol once per cycle. Without this cache,
            # the first strategy using a symbol would consume the previous price
            # and later strategies would incorrectly see HOLD on the same quote.
            cycle_signals: dict[str, tuple[object, str, float]] = {}
            for strategy in strategies:
                portfolio=db.get(Portfolio, strategy.portfolio_id)
                if not portfolio: continue
                for symbol in [s.strip().upper() for s in strategy.symbols.split(',') if s.strip()]:
                    try:
                        if symbol not in cycle_signals:
                            q=market_data.quote(symbol, force=True)
                            signal, confidence=self._signal(symbol, q.price)
                            cycle_signals[symbol]=(q, signal, confidence)
                        q, signal, confidence = cycle_signals[symbol]
                        signals.append({'strategy_id':strategy.id,'symbol':symbol,'signal':signal,'confidence':confidence,'price':q.price})
                        self.stats.signals += 1
                        ok, reason=self._eligible(db,strategy,portfolio,symbol,signal,confidence,q.price)
                        if not ok: continue
                        pos=db.scalar(select(Position).where(Position.portfolio_id==portfolio.id,Position.symbol==symbol))
                        if signal == 'BUY':
                            qty=round(self._buy_quantity(strategy,portfolio,q.price,db),6)
                        else:
                            qty=round(pos.quantity,6)
                        if qty <= 0: self.stats.rejected += 1; continue
                        gross=qty*q.price
                        if signal == 'BUY' and gross*(1+settings.commission_bps/10000) > portfolio.cash:
                            self.stats.rejected += 1; continue
                        from .app import order, OrderIn
                        result=order(OrderIn(symbol=symbol,side=signal,quantity=qty,price=q.price,reason=f'strategy:{strategy.name}',signal=signal), _RequestProxy(), portfolio.user, db)
                        self._last_action[(strategy.id,symbol)]=datetime.now(timezone.utc).timestamp()
                        strategy.last_action=datetime.now(timezone.utc)
                        strategy.total_orders += 1
                        self.stats.orders += 1
                        actions.append({'strategy_id':strategy.id,'symbol':symbol,'side':signal,'quantity':qty,'price':q.price,'result':result})
                    except MarketDataError as exc: errors.append(str(exc)); self.stats.errors += 1
                    except Exception as exc: errors.append(str(exc)); self.stats.errors += 1
            db.commit(); self.stats.cycles += 1; self.stats.last_cycle=datetime.now(timezone.utc)
            return {'strategies':len(strategies),'signals':signals,'orders':actions,'errors':errors,'timestamp':self.stats.last_cycle}
        finally: db.close()

class _RequestProxy:
    headers={}

strategy_engine=StrategyEngine()

def backtest_strategy(prices: list[float], min_move_pct: float=0.25, position_size_pct: float=10.0, commission_bps: float=10.0) -> dict:
    """Deterministic long-only momentum backtest over supplied close prices."""
    if len(prices) < 2: raise ValueError('at least 2 prices required')
    if any(p <= 0 for p in prices): raise ValueError('prices must be positive')
    cash=100000.0; qty=0.0; entry=0.0; trades=[]; equity=[]; prev=prices[0]
    for i, price in enumerate(prices):
        if i == 0: equity.append(cash); continue
        ret=(price/prev-1)*100; prev=price
        if qty == 0 and ret > min_move_pct:
            budget=cash*position_size_pct/100; q=budget/price; fee=budget*commission_bps/10000
            if cash >= budget+fee: cash-=budget+fee; qty=q; entry=price; trades.append({'index':i,'side':'BUY','price':price,'quantity':q})
        elif qty > 0 and ret < -min_move_pct:
            gross=qty*price; fee=gross*commission_bps/10000; pnl=(price-entry)*qty-fee; cash+=gross-fee; trades.append({'index':i,'side':'SELL','price':price,'quantity':qty,'realized_pnl':pnl}); qty=0; entry=0
        equity.append(cash+qty*price)
    if qty:
        price=prices[-1]; gross=qty*price; fee=gross*commission_bps/10000; pnl=(price-entry)*qty-fee; cash+=gross-fee; trades.append({'index':len(prices)-1,'side':'SELL','price':price,'quantity':qty,'realized_pnl':pnl}); qty=0
    peak=equity[0]; max_dd=0.0
    for v in equity:
        peak=max(peak,v); max_dd=max(max_dd,(peak-v)/peak*100)
    total_return=(cash/100000-1)*100
    return {'initial_equity':100000.0,'final_equity':round(cash,2),'total_return_pct':round(total_return,4),'max_drawdown_pct':round(max_dd,4),'trades':trades,'trade_count':len(trades)}

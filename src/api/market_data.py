from __future__ import annotations
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    timestamp: datetime
    source: str = 'yahoo_finance'
    previous_close: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None

class MarketDataError(RuntimeError):
    pass

class MarketData:
    """Thread-safe market-data adapter.

    Yahoo Finance is used as the default public data adapter. It is useful for
    research/paper trading, but it is not an exchange-certified tick feed and
    availability/latency can vary. A production tick feed can be plugged into
    this adapter later without changing the mobile API.
    """
    def __init__(self, ttl_seconds: float = 5.0):
        self.ttl_seconds = max(0.0, ttl_seconds)
        self._cache: dict[str, Quote] = {}
        self._history_cache: dict[tuple[str, str], tuple[datetime, pd.DataFrame]] = {}
        self._lock = threading.RLock()

    def _ticker(self, symbol: str):
        import yfinance as yf
        return yf.Ticker(symbol)

    def quote(self, symbol: str, force: bool = False) -> Quote:
        symbol = symbol.strip().upper()
        if not symbol:
            raise MarketDataError('symbol is required')
        with self._lock:
            cached = self._cache.get(symbol)
            if cached and not force and (datetime.now(timezone.utc) - cached.timestamp).total_seconds() < self.ttl_seconds:
                return cached
        try:
            ticker = self._ticker(symbol)
            price = previous = opn = high = low = volume = None
            try:
                fast = ticker.fast_info
                price = fast.get('last_price') or fast.get('regular_market_price')
                previous = fast.get('previous_close')
                opn = fast.get('open')
                high = fast.get('day_high')
                low = fast.get('day_low')
                volume = fast.get('last_volume')
            except Exception:
                pass
            if price is None or previous is None or opn is None or high is None or low is None:
                hist = ticker.history(period='5d', interval='1d', auto_adjust=False)
                if hist.empty:
                    raise MarketDataError(f'No market data returned for {symbol}')
                close = hist['Close'].dropna()
                price = float(close.iloc[-1])
                if len(close) >= 2:
                    previous = float(close.iloc[-2])
                row = hist.iloc[-1]
                opn = float(row['Open']) if pd.notna(row['Open']) else None
                high = float(row['High']) if pd.notna(row['High']) else None
                low = float(row['Low']) if pd.notna(row['Low']) else None
                volume = float(row['Volume']) if pd.notna(row['Volume']) else None
            price = float(price)
            if price <= 0:
                raise MarketDataError(f'Invalid market price for {symbol}')
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError(f'Unable to fetch quote for {symbol}: {exc}') from exc
        q = Quote(symbol, price, datetime.now(timezone.utc), 'yahoo_finance',
                  float(previous) if previous is not None else None,
                  float(opn) if opn is not None else None,
                  float(high) if high is not None else None,
                  float(low) if low is not None else None,
                  float(volume) if volume is not None else None)
        with self._lock:
            self._cache[symbol] = q
        return q

    def quotes(self, symbols: Iterable[str], force: bool = False) -> list[Quote]:
        out = []
        errors = []
        for symbol in symbols:
            try:
                out.append(self.quote(symbol, force=force))
            except MarketDataError as exc:
                errors.append(str(exc))
        if errors and not out:
            raise MarketDataError('; '.join(errors))
        return out

    def history(self, symbol: str, range_key: str = '1d', force: bool = False) -> pd.DataFrame:
        symbol = symbol.strip().upper()
        ranges = {
            '1d': ('1d', '5m'), '5d': ('5d', '15m'), '1m': ('1mo', '1h'),
            '6m': ('6mo', '1d'), '1y': ('1y', '1d'), '5y': ('5y', '1wk'),
        }
        if range_key not in ranges:
            raise MarketDataError('range must be one of 1d, 5d, 1m, 6m, 1y, 5y')
        cache_key = (symbol, range_key)
        now = datetime.now(timezone.utc)
        with self._lock:
            cached = self._history_cache.get(cache_key)
            if cached and not force and (now - cached[0]).total_seconds() < self.ttl_seconds:
                return cached[1].copy()
        try:
            period, interval = ranges[range_key]
            hist = self._ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
            if hist.empty:
                raise MarketDataError(f'No historical data returned for {symbol}')
            cols = [c for c in ('Open', 'High', 'Low', 'Close', 'Volume') if c in hist.columns]
            hist = hist[cols].dropna(subset=['Close']).copy()
            if len(hist) > 400:
                hist = hist.tail(400)
            with self._lock:
                self._history_cache[cache_key] = (now, hist.copy())
            return hist
        except MarketDataError:
            raise
        except Exception as exc:
            raise MarketDataError(f'Unable to fetch history for {symbol}: {exc}') from exc

    def snapshot(self) -> dict[str, Quote]:
        with self._lock:
            return dict(self._cache)

market_data = MarketData()

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now(): return datetime.now(timezone.utc)

class User(Base):
    __tablename__='users'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    email: Mapped[str]=mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(512))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    portfolio: Mapped['Portfolio'] = relationship(back_populates='user', uselist=False, cascade='all, delete-orphan')

class Portfolio(Base):
    __tablename__='portfolios'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'), unique=True)
    initial_cash: Mapped[float]=mapped_column(Float, default=100000.0)
    cash: Mapped[float]=mapped_column(Float, default=100000.0)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User]=relationship(back_populates='portfolio')
    orders: Mapped[list['Order']]=relationship(cascade='all, delete-orphan')
    positions: Mapped[list['Position']]=relationship(cascade='all, delete-orphan')
    trades: Mapped[list['Trade']]=relationship(cascade='all, delete-orphan')
    decisions: Mapped[list['Decision']]=relationship(cascade='all, delete-orphan')

class Order(Base):
    __tablename__='orders'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(ForeignKey('portfolios.id'), index=True)
    symbol: Mapped[str]=mapped_column(String(32), index=True)
    side: Mapped[str]=mapped_column(String(8))
    quantity: Mapped[float]=mapped_column(Float)
    price: Mapped[float]=mapped_column(Float)
    status: Mapped[str]=mapped_column(String(16), default='FILLED')
    reason: Mapped[str|None]=mapped_column(Text, nullable=True)
    signal: Mapped[str|None]=mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str|None]=mapped_column(String(128), nullable=True, unique=True, index=True)
    timestamp: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class Position(Base):
    __tablename__='positions'
    __table_args__=(UniqueConstraint('portfolio_id','symbol'),)
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(ForeignKey('portfolios.id'), index=True)
    symbol: Mapped[str]=mapped_column(String(32), index=True)
    quantity: Mapped[float]=mapped_column(Float, default=0)
    avg_price: Mapped[float]=mapped_column(Float, default=0)
    market_price: Mapped[float]=mapped_column(Float, default=0)
    stop_loss: Mapped[float|None]=mapped_column(Float, nullable=True)
    take_profit: Mapped[float|None]=mapped_column(Float, nullable=True)

class Trade(Base):
    __tablename__='trades'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(ForeignKey('portfolios.id'), index=True)
    order_id: Mapped[int]=mapped_column(ForeignKey('orders.id'))
    symbol: Mapped[str]=mapped_column(String(32))
    side: Mapped[str]=mapped_column(String(8))
    quantity: Mapped[float]=mapped_column(Float)
    price: Mapped[float]=mapped_column(Float)
    realized_pnl: Mapped[float]=mapped_column(Float, default=0)
    reason: Mapped[str|None]=mapped_column(Text, nullable=True)
    signal: Mapped[str|None]=mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)


class Strategy(Base):
    __tablename__='strategies'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(ForeignKey('portfolios.id'), index=True)
    name: Mapped[str]=mapped_column(String(100))
    symbols: Mapped[str]=mapped_column(Text)
    enabled: Mapped[bool]=mapped_column(default=False)
    min_confidence: Mapped[float]=mapped_column(Float, default=50.0)
    position_size_pct: Mapped[float]=mapped_column(Float, default=10.0)
    max_exposure_pct: Mapped[float]=mapped_column(Float, default=25.0)
    max_open_positions: Mapped[int]=mapped_column(Integer, default=3)
    cooldown_seconds: Mapped[int]=mapped_column(Integer, default=300)
    total_orders: Mapped[int]=mapped_column(Integer, default=0)
    last_action: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

class Decision(Base):
    __tablename__='decisions'
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int]=mapped_column(ForeignKey('portfolios.id'), index=True)
    symbol: Mapped[str]=mapped_column(String(32), index=True)
    signal: Mapped[str]=mapped_column(String(32))
    confidence: Mapped[float]=mapped_column(Float)
    regime: Mapped[str|None]=mapped_column(String(64), nullable=True)
    explanation: Mapped[str|None]=mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=now)

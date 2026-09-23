from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def now(): return datetime.now(timezone.utc)

class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int|None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[str|None] = mapped_column(String(64), nullable=True, index=True)
    detail: Mapped[str|None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

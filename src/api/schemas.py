from __future__ import annotations
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class RegisterIn(BaseModel): email: EmailStr; password: str = Field(min_length=8, max_length=128)
class LoginIn(BaseModel): email: EmailStr; password: str
class TokenOut(BaseModel): access_token: str; token_type: str='bearer'
class OrderIn(BaseModel):
    symbol: str=Field(min_length=1,max_length=32); side: str; quantity: float=Field(gt=0); price: float=Field(gt=0)
    reason: str|None=None; signal: str|None=None; idempotency_key: str|None=Field(default=None,max_length=128)
class MarketOrderIn(BaseModel):
    symbol: str=Field(min_length=1,max_length=32)
    side: str
    quantity: float=Field(gt=0)
    reason: str|None=None
    signal: str|None=None
    idempotency_key: str|None=Field(default=None,max_length=128)

class DecisionIn(BaseModel): symbol: str; signal: str; confidence: float=Field(ge=0,le=100); regime: str|None=None; explanation: str|None=None
class UserOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:int; email:str
class Page(BaseModel): items: list; next_cursor: int|None=None

class StrategyIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    symbols: str = Field(min_length=1, max_length=1000)
    enabled: bool = False
    min_confidence: float = Field(default=50, ge=0, le=100)
    position_size_pct: float = Field(default=10, gt=0, le=100)
    max_exposure_pct: float = Field(default=25, gt=0, le=100)
    max_open_positions: int = Field(default=3, ge=1, le=100)
    cooldown_seconds: int = Field(default=300, ge=0, le=86400)

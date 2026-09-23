from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv('DATABASE_URL', 'sqlite:///./data/trading.db')
    jwt_secret: str = os.getenv('JWT_SECRET', 'dev-only-change-me')
    jwt_expire_minutes: int = int(os.getenv('JWT_EXPIRE_MINUTES', '1440'))
    commission_bps: float = float(os.getenv('COMMISSION_BPS', '5'))
    allowed_origins: str = os.getenv('ALLOWED_ORIGINS', 'http://localhost:8501')
    webhook_url: str | None = os.getenv('WEBHOOK_URL') or None
    environment: str = os.getenv('ENVIRONMENT', 'development')
    require_secure_config: bool = os.getenv('REQUIRE_SECURE_CONFIG', 'false').lower() == 'true'

    def validate(self) -> None:
        if self.jwt_expire_minutes <= 0: raise ValueError('JWT_EXPIRE_MINUTES must be positive')
        if self.commission_bps < 0: raise ValueError('COMMISSION_BPS cannot be negative')
        if self.require_secure_config and (self.jwt_secret == 'dev-only-change-me' or len(self.jwt_secret) < 32):
            raise ValueError('JWT_SECRET must be a strong secret in secure mode')
        if self.environment == 'production' and self.allowed_origins.strip() == '*':
            raise ValueError('ALLOWED_ORIGINS cannot be * in production')

settings = Settings()

# AI Trading Research & Paper-Trading Platform

## V0.5 — Intelligent Stock Screener

V0.5 builds on the V0.4 multi-symbol foundation and adds a configurable rule-based stock screener.

### Added
- Custom AND-condition screener
- Price, RSI, relative-volume, return, volatility and SMA-distance filters
- Saved scan definitions in `configs/saved_scans.json`
- Latest-match results across all downloaded symbols
- Screener unit tests
- V0.4 watchlists, scanners and comparisons retained

### Example scan
- Close > 0
- RSI (14) < 70
- Relative Volume > 1.5
- 20D Return (%) > 0
- SMA 50 Distance (%) > 0

All conditions must pass for a symbol to match.

### Run

```bash
pip install -r requirements.txt
python -m src.data.downloader
streamlit run app/dashboard.py
pytest -q
```

### Scope
This release is a research screener, not an execution system. It does not place trades, claim predictive accuracy, or imply that historical technical conditions guarantee future performance.


## V0.6 — Machine Learning Research

Adds a research-only ML layer with:
- forward-return labels with configurable horizon/threshold
- strict chronological train/test split
- Logistic Regression baseline
- Random Forest
- optional XGBoost
- time-series-aware sigmoid probability calibration
- accuracy, precision, recall, ROC AUC, Brier score and log loss
- model-specific feature importance
- latest-row probability snapshot
- Streamlit ML Research tab
- tests for label alignment and chronological splitting

Important: model probabilities and historical test metrics are research diagnostics, not guarantees of future returns or profitability.

Run:
```bash
pip install -r requirements.txt
pytest -q
streamlit run app/dashboard.py
```


## V0.7 — AI Intelligence Engine

Adds a transparent intelligence layer on top of V0.6:
- ensemble model signal from calibrated probabilities
- confidence score based on directional strength and model agreement
- broad market-regime classification
- aggregated feature-based signal explanation
- model-health diagnostics using out-of-sample metrics
- Streamlit AI Intelligence tab

Confidence is a diagnostic score, not a probability of profit or a trading guarantee.


## V0.8 — Scientific Backtesting

Adds a research-only backtesting engine in `src/backtesting/backtester.py`:
- next-bar-open execution to avoid lookahead
- commission and slippage
- fractional position sizing
- stop-loss / take-profit controls
- equity curve and trade journal
- return, CAGR, volatility, Sharpe, Sortino, drawdown, win-rate and profit-factor metrics
- chronological walk-forward evaluation
- Monte Carlo bootstrap of completed trade returns

The dashboard exposes the feature under **📈 V0.8 Scientific Backtesting**.
Backtests are simulations for research/paper trading only and do not imply future profitability.


## V0.9 — Advanced Paper Trading

Adds `src/paper_trading/engine.py` with:
- virtual cash and positions
- simulated market orders with commission
- realized/unrealized P&L
- order status and reasons
- persistent JSON-compatible portfolio snapshots
- chronological decision replay using next-bar-open fills
- trade/order journal for auditability

The dashboard exposes this under **💼 V0.9 Advanced Paper Trading**.
No broker connectivity or live execution is included.

## V1.0 Production + Mobile API

The platform now includes a FastAPI REST service for authenticated paper trading and mobile clients. It uses SQLAlchemy persistence (SQLite by default; PostgreSQL is supported through `DATABASE_URL` with the appropriate PostgreSQL driver), bearer-token authentication, CORS configuration, order/position/trade/decision endpoints, and optional webhook notifications. No broker execution is implemented.

### Run API locally

```bash
uvicorn src.api.app:app --reload --port 8000
```

OpenAPI docs are available at `/docs`. Copy `.env.example` to `.env` and set a strong `JWT_SECRET` before deployment. For PostgreSQL, set `DATABASE_URL` and install a compatible SQLAlchemy PostgreSQL driver.

### Docker

```bash
docker compose up --build
```

## V1.1 — Production Hardening
- Security headers and request IDs
- Database readiness endpoint
- Login rate limiting
- Idempotent order retries
- Audit event trail
- Paginated order/trade/decision APIs
- Alembic migration for production databases
- Secure production configuration checks
- Mobile API contract

## V1.4 — Production Infrastructure
- PostgreSQL + Redis Docker services
- Shared Redis rate limiting when `REDIS_URL` is configured
- Redis-backed job queue with local development fallback
- API request/error/latency metrics
- Mobile API contract hardened for unreliable networks
- Production deployment checklist in `deploy/V1.4_PRODUCTION.md`

## V1.5 — Event-driven paper trading

V1.5 adds a background paper-trading monitor. It refreshes open-position quotes, updates mark-to-market prices, detects stop-loss/take-profit triggers, and exposes engine status/start/stop/run-once API endpoints. It remains paper-trading-only; risk triggers are reported to the application layer and no broker order is ever submitted.


## V1.6.1 — Reliability fixes
- Fixed RSI warm-up behavior for one-sided price series so valid RSI values are produced instead of all-NaN output.
- Kept extreme close-to-close moves as validation warnings without cascading the same outlier into an OHLC hard error.
- Added regression coverage for the RSI behavior.

## V1.6 — Strategy Automation
- Persistent per-user paper strategies with symbol lists and risk controls.
- Configurable minimum signal confidence, position sizing, maximum exposure, open-position cap, and cooldown.
- Start/stop/run-once strategy engine.
- Automated momentum-driven paper entries/exits with existing order/audit infrastructure.
- Deterministic strategy backtest endpoint for supplied price series.
- No broker execution; all automation remains paper-only.


## V1.8.0 — Market Terminal + AI Mobile
- Mobile Markets terminal with auto-refreshing market snapshots.
- Broad discovery universe for Indian/global indices, Indian stocks, commodities, FX and crypto.
- Arbitrary Yahoo Finance symbols can be opened for supported instruments.
- Multi-range OHLC candlestick charts: 1D, 5D, 1M, 6M, 1Y, 5Y.
- AI Intelligence screen exposing market regime, RSI, MACD, SMA context and existing ML research diagnostics.
- Paper portfolio remains separate from market-data research and no broker execution is added.
- The default Yahoo Finance adapter is not an exchange-certified tick feed; a licensed real-time provider is required for guaranteed tick-level coverage.

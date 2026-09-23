# Deployment

## Production checklist
1. Set a random `JWT_SECRET` of at least 32 characters and `REQUIRE_SECURE_CONFIG=true`.
2. Set `ENVIRONMENT=production` and explicit `ALLOWED_ORIGINS` values.
3. Use PostgreSQL (`DATABASE_URL=postgresql+psycopg://...`) and install `psycopg[binary]`.
4. Run `alembic upgrade head` before starting the API.
5. Put TLS/reverse proxy and a shared rate limiter (Redis/API gateway) in front of multiple instances.
6. Back up PostgreSQL and restrict database/network access.
7. Keep this system in paper-trading mode; no broker execution is exposed by this API.

## Commands
```bash
alembic upgrade head
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

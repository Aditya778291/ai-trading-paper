# AI Trading Paper v1.7.0 — QA Report

Date: 2026-09-02

## Automated backend tests

`PYTHONPATH=. pytest -q`

**Result: 54 passed, 0 failed.**

Warnings: JWT test fixtures intentionally use short test secrets. Production configuration requires `REQUIRE_SECURE_CONFIG=true` and a JWT secret of at least 32 characters.

## Android release configuration

- Expo SDK: 54
- React Native: 0.81.x
- Android target/compile API: 36 through Expo SDK 54
- Android package: `com.aitrading.paper`
- Version: `1.7.0`
- Android versionCode: `7`
- Production EAS profile: Android App Bundle (`.aab`)
- Production networking: HTTPS only
- Account creation: included
- In-app account deletion: included
- App behavior: paper trading only; no broker execution

## Manual Play testing checklist

1. Fresh install.
2. Create account with valid email/password.
3. Reject/handle invalid credentials without crashing.
4. Sign in and load portfolio.
5. Submit paper BUY order.
6. Submit paper SELL order.
7. Refresh and confirm order history.
8. Sign out and sign back in.
9. Delete account and confirm session is invalidated.
10. Relaunch after account deletion.
11. Test with network unavailable; app must show an error instead of crashing.
12. Test Android back gesture/navigation and keyboard input.
13. Run Google Play pre-launch report and resolve any device-specific issues.

Automated tests cannot prove Google Play policy approval. Store metadata, privacy disclosures, data-safety answers, financial-services declarations, tester requirements and reviewer access must also be completed accurately.


## V1.8.0 verification (2026-09-19)
- Python syntax/import compilation: PASS (`python -m compileall -q src app tests`).
- Automated backend tests: PASS — 54 passed.
- API smoke test: PASS — `/api/health` and `/api/ready` returned 200.
- Fresh SQLite Alembic migration to `0003_strategy_automation`: PASS.
- Fixed Alembic revision chain (`0002` now follows revision `0001`) and made risk/strategy migrations safe on fresh current-schema databases.
- Fixed strategy engine signal reuse so multiple enabled strategies on the same symbol receive the same cycle signal instead of consuming each other's previous-price state.
- Updated API health version to 1.8.0 and corresponding version assertions.
- Mobile development API validation now permits private LAN HTTP only in Expo development; production still requires HTTPS.
- Mobile dependency installation and Expo runtime were not executable in this environment because external package-network access is unavailable; run `npm install` and `npx expo-doctor` on the development PC.
- Live Yahoo Finance quote/history access was not validated here because `yfinance` is not installed in the sandbox and external package/data network access is unavailable. The dependency remains declared in `requirements.txt`.

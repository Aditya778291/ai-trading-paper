# v1.7.1 release checklist

## Required before building the Play Store AAB

Set the production API origin as a public HTTPS URL. Do not use localhost, 127.0.0.1, a LAN IP, or HTTP.

```bash
eas env:create --name EXPO_PUBLIC_API_BASE_URL --value https://YOUR-DEPLOYED-API --environment production --visibility plaintext
```

Then build:

```bash
eas build --platform android --profile production
```

The production profile is configured to produce an Android App Bundle (`.aab`).

## Backend

The API must expose:

- `GET /api/health`
- `GET /api/ready`
- `POST /api/auth/register`
- `POST /api/auth/login`

For production, set `DATABASE_URL`, `JWT_SECRET` (32+ characters), `ENVIRONMENT=production`, `REQUIRE_SECURE_CONFIG=true`, and `ALLOWED_ORIGINS`.

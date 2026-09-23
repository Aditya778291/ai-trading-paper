# Mobile Client — V1.8.0

Expo/React Native client for the paper-trading API. It includes login, registration, portfolio, recent orders, and paper BUY/SELL order entry.

## Production configuration

The Android/iOS app reads `EXPO_PUBLIC_API_BASE_URL` at build time. It must be a **public HTTPS API origin**, for example `https://api.example.com`.

Do not use `localhost`, `127.0.0.1`, a private LAN IP, or an HTTP URL in a tester build.

### Local development
```bash
npm install
EXPO_PUBLIC_API_BASE_URL=http://YOUR-LAN-IP:8000 npx expo start
```

### Production build
Set the EAS environment variable before building:
```bash
eas env:create --name EXPO_PUBLIC_API_BASE_URL --value https://YOUR-PUBLIC-API-DOMAIN --environment production --visibility plaintext
eas build --platform android --profile production
```

The value is intentionally not committed to source control. The build will fail gracefully with a clear configuration error if it is missing instead of showing the misleading Android `Network request failed` error.

Orders remain paper-only.

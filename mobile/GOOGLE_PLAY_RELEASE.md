# Google Play release checklist

## Before building
1. Deploy the backend at a public HTTPS URL.
2. Replace `expo.extra.apiBaseUrl` in `app.json` with that HTTPS URL.
3. Set `ENVIRONMENT=production`, `REQUIRE_SECURE_CONFIG=true`, a random `JWT_SECRET` of at least 32 characters, and production `ALLOWED_ORIGINS` on the server.
4. Do not ship `http://localhost:8000` or any HTTP API endpoint.

## Build
```bash
npm install
npx expo-doctor
npx eas login
npx eas build:configure
npx eas build --platform android --profile production
```
The production profile is configured to produce an Android App Bundle (`.aab`).

## Play Console
1. Create app: **AI Trading Paper**.
2. Default language: choose your actual listing language.
3. App type: App; category should reflect the actual app functionality.
4. Upload the `.aab` to **Internal testing** first.
5. Add tester accounts and test registration, login, paper BUY/SELL, refresh, sign out, and account deletion.
6. Complete **App content** declarations, including privacy policy, ads declaration, app access instructions, target audience/content, and financial-services declarations if Play presents them for this app.
7. Complete **Data safety** based on the final backend/data-processing configuration. Do not guess these answers.
8. Complete store listing, screenshots, icon, contact details and support/privacy URLs.
9. Run Play pre-launch report and fix all crashes or policy blockers.
10. If Google requires closed testing for your account, complete the displayed tester requirement before applying for production access.
11. Create the production release only after internal/closed testing is clean.

## Important
Google Play approval cannot be guaranteed by code alone. Reviewers can reject an app for policy, metadata, privacy, misleading claims, broken backend access, or other issues even when automated tests pass.

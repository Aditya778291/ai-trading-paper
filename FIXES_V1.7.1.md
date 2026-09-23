# v1.7.1 Play-test reliability fixes

## Fixed
- Production mobile builds now read `EXPO_PUBLIC_API_BASE_URL` at build time instead of relying on the placeholder value in `app.json`.
- Added a dynamic Expo config so EAS production builds receive the configured public API URL.
- Added explicit Android `INTERNET` permission.
- Added a 15-second API timeout and clearer network/configuration error messages.
- Added a request ID to mobile API calls for easier backend diagnostics.
- Fixed backend CORS to allow the account-deletion `DELETE` request.
- Added `render.yaml` as a deployment template for the API.
- Bumped mobile version to 1.7.1 / Android versionCode 8.

## Critical deployment requirement
The app still requires a real public HTTPS API server. The source intentionally does **not** contain a fake or private server address.

Before the Play tester build, set:
`EXPO_PUBLIC_API_BASE_URL=https://<your-public-api-domain>`

Do not use localhost, 127.0.0.1, a LAN IP, or HTTP.

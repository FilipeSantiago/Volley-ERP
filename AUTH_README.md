# Auth API

## Endpoints

### `GET /auth/google/start`
- Query:
  - `redirect_uri` (optional)
  - `platform` (optional)
- Response:
  - `auth_url`
  - `callback_mode` (`json` or `redirect`)
  - `redirect_uri` (only when provided/valid)

### `GET /auth/google/callback`
- Query from Google OAuth: `state`, `code` or `error/error_description`.
- Behavior:
  - Valid state + success:
    - JSON mode: returns `status`, `customer_id`, `google_sub`, `email`, `doc_id`, `access_token`, `refresh_token`, `token_type`, `expires_in`.
    - Redirect mode:
      - `http/https`: `302` to `<redirect_uri>#payload=<urlencoded-json>` where payload includes `access_token`, `token_type`, `refresh_token`.
      - custom scheme: `302` with query params `access_token`, `token_type`, `refresh_token`.
  - Provider errors in redirect mode: `302` with query params `error` and `error_description`.

### `POST /auth/google/mobile`
- JSON body:
  - `authorization_code`
  - `code_verifier` (43–128 chars, PKCE charset)
  - `redirect_uri`
  - `platform` (`android` or `ios`)
  - `device_info` (optional)
- Response:
  - `status`, `customer_id`, `google_sub`, `email`, `doc_id`, token pair fields.

### `POST /security/refresh`
- JSON body: `refresh_token`
- Response: token pair (`access_token`, `refresh_token`, `token_type`, `expires_in`)

### `GET /security/me`
- Auth: `Authorization: Bearer <access_token>`
- Response:
  - `customer_id`
  - `google_sub`
  - `email`
  - `doc_id`

### `POST /customer/workspace` (protected)
- Auth: `Authorization: Bearer <access_token>`
- JSON body:
  - `workspace_name` (optional)
- Response:
  - workspace info and re-issued token pair.

## Token Contract
- Pair response fields:
  - `access_token`
  - `refresh_token`
  - `token_type` = `Bearer`
  - `expires_in` (access TTL in seconds, default `600`)
- Access TTL default: `600`
- Refresh TTL default: `604800`
- JWT claims:
  - required: `iss`, `aud`, `sub`, `type`, `iat`, `nbf`, `exp`, `jti`
  - optional: `email`, `google_sub`, `doc_id`

## Error contract
- Missing bearer token: `401 {"error":"unauthorized"}` + `WWW-Authenticate: Bearer`
- Invalid token: `401 {"error":"invalid_token"}`
- Expired token: `401 {"error":"token_expired"}`
- Invalid state: `400 {"error":"invalid_state", ...}`
- Invalid redirect: `400 {"error":"invalid_redirect_uri", ...}`
- Invalid OAuth code: `400 {"error":"invalid_code", ...}`

## Environment variables
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `GOOGLE_OAUTH_ANDROID_CLIENT_ID`
- `GOOGLE_OAUTH_ANDROID_CLIENT_SECRET`
- `GOOGLE_OAUTH_IOS_CLIENT_ID`
- `GOOGLE_OAUTH_IOS_CLIENT_SECRET`
- `AUTH_STATE_SECRET`
- `JWT_ACCESS_SECRET`
- `JWT_REFRESH_SECRET`
- `JWT_ISSUER`
- `JWT_AUDIENCE`
- `JWT_ACCESS_TTL_SECONDS`
- `JWT_REFRESH_TTL_SECONDS`
- `AUTH_REDIRECT_ALLOWED_ORIGINS`
- `AUTH_REDIRECT_ALLOWED_SCHEMES`
- `AUTH_MOBILE_ALLOWED_PLATFORMS`
- `AUTH_MOBILE_REDIRECT_ALLOWED_ANDROID`
- `AUTH_MOBILE_REDIRECT_ALLOWED_IOS`
- `TOKEN_ENC_KEY`
- Optional secret manager fallback: `TOKEN_ENC_KEY_SECRET_NAME`
- `GOOGLE_AUTH_MODE` (`adc` default; supports `adc`, `service_account`, `auto`)
- `GOOGLE_SERVICE_ACCOUNT_JSON` (optional, only for service account mode/fallback)
- `GOOGLE_APPLICATION_CREDENTIALS` (optional, only for service account mode/fallback)
- `GOOGLE_CLOUD_PROJECT` (optional, used by Firestore client)
- `FIRESTORE_DATABASE_ID` (optional, default: `customer`)
- `FIRESTORE_CUSTOMERS_COLLECTION` (optional, default: `customers`)

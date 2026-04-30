# Volley ERP Auth + Org Model

## Core Auth Endpoints

### `GET /auth/google/start`
- Returns Google OAuth `auth_url`, `callback_mode`, optional validated `redirect_uri`.
- Does **not** create organization/workspace/team.

### `GET /auth/google/callback`
- Upserts app `user` + encrypted Google connection.
- Returns:
  - `status`
  - `user_id`
  - `google_sub`
  - `email`
  - `organizations`
  - token pair fields
- Does **not** create workspace.

### `POST /auth/google/mobile`
- Same identity behavior as callback flow (PKCE path).
- Does **not** create workspace.

### `POST /security/refresh`
- Re-issues app JWT pair.
- Does **not** create workspace.

### `GET /security/me`
- Returns:
  - `user_id`
  - `google_sub`
  - `email`
  - `organizations` with visible teams.

## Organization / Team / Invite Endpoints

### Organization
- `POST /organizations`
- `GET /organizations`
- `GET /organizations/{org_id}`
- `POST /organizations/{org_id}/workspace/ensure`
- `GET /organizations/{org_id}/members`
- `DELETE /organizations/{org_id}/members/{user_id}`

### Team
- `POST /organizations/{org_id}/teams`
- `GET /organizations/{org_id}/teams`
- `GET /organizations/{org_id}/teams/{team_id}`
- `POST /organizations/{org_id}/teams/{team_id}/members`
- `GET /organizations/{org_id}/teams/{team_id}/members`

### Invite
- `POST /organizations/{org_id}/invites`
- `POST /organizations/invites/accept`

## Control Plane vs BYOS
- Firestore is source of truth for users, organizations, memberships, teams, invites, and workspace IDs.
- Google Drive/Sheets store business data only.
- Authorization does not depend on Google Sheets.

## Token Contract
- Keeps:
  - `access_token`
  - `refresh_token`
  - `token_type = Bearer`
  - `expires_in`
- JWT required claims unchanged: `iss`, `aud`, `sub`, `type`, `iat`, `nbf`, `exp`, `jti`.
- Optional claims: `email`, `google_sub`.

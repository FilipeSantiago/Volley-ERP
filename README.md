# Volley ERP Backend

FastAPI backend for a volleyball operations platform with Google OAuth login, Firestore-backed authorization, and Google Drive/Sheets as the workspace and data store.

## Implemented Features

### Authentication

- Google OAuth web login start flow at `GET /auth/google/start`
- Google OAuth callback handling at `GET /auth/google/callback`
- Two callback modes:
  - JSON response mode when no frontend redirect URI is provided
  - Redirect mode when `redirect_uri` is provided and allowed
- Google mobile auth code exchange with PKCE at `POST /auth/google/mobile`
- JWT access and refresh token issuance
- JWT refresh at `POST /security/refresh`
- Authenticated profile lookup at `GET /security/me`
- Signed state token validation for web OAuth callbacks
- Redirect URI allowlists for web and mobile OAuth clients
- Separate mobile OAuth client handling for Android and iOS
- Refresh token encryption before persistence
- Reuse of previously stored Google refresh tokens when Google does not send a new one

### Organization Management

- Create organizations at `POST /organizations`
- List organizations visible to the authenticated user at `GET /organizations`
- Fetch a single organization at `GET /organizations/{org_id}`
- List organization members at `GET /organizations/{org_id}/members`
- Remove organization members at `DELETE /organizations/{org_id}/members/{user_id}`
- Organization creation automatically provisions a Google Drive workspace
- Workspace repair/reconciliation endpoint at `POST /organizations/{org_id}/workspace/ensure`

### Invitations and Membership

- Create organization or team-scoped invites at `POST /organizations/{org_id}/invites`
- Accept invites at `POST /organizations/invites/accept`
- Invite tokens are generated securely and only stored as hashes
- Invite acceptance validates:
  - token existence
  - pending status
  - expiration
  - invited email matching the authenticated user email
- Accepting a team invite auto-creates an org membership if needed
- Creating a new invite revokes pending invites for the same scope/email target

### Team Management

- Create teams at `POST /teams`
- List teams visible to the authenticated user at `GET /teams`
- Fetch a single team at `GET /teams/detail`
- Create a Google Sheets spreadsheet for a team during team creation
- Lazy spreadsheet provisioning for athlete operations when a team exists without a sheet
- Add team members at `POST /teams/members`
- List team members at `GET /teams/members`
- Adding a team member supports two paths:
  - immediate membership if the user already exists
  - invite issuance if the email does not belong to an existing user

### Athletes

- Create athletes with multipart form uploads at `POST /athletes`
- Update athletes with optional photo replacement at `PUT /athletes`
- List athletes for a specific team at `GET /athletes?org_id=...&team_id=...`
- List athletes across all accessible teams in an organization for org admins/owners by omitting `team_id`
- Fetch athlete photo binary content at `GET /athletes/photo/{athlete_id}`
- Athlete records support:
  - full name
  - birthday
  - CPF
  - cellphone
  - position
  - T-shirt size
  - shorts size
  - RG
  - email
  - photo upload
- Birthday parsing accepts both `YYYY-MM-DD` and `DD/MM/YYYY`
- Uploaded photo filenames are sanitized before storage

### Coach

- Create a team coach with photo upload at `POST /coach`
- Update coach data with optional photo replacement at `PUT /coach`
- Fetch coach data at `GET /coach`
- Fetch coach photo binary content at `GET /coach/photo`
- Coach records support athlete-like personal fields plus `pix_key`

### Monthly Fees

- List recurring monthly fee rules at `GET /monthly_fees`
- Create recurring monthly fee rules at `POST /monthly_fees`
- Update recurring monthly fee rules at `PUT /monthly_fees/{fee_id}`
- Soft-delete recurring monthly fee rules at `DELETE /monthly_fees/{fee_id}`
- Implemented tags:
  - `MONTHLY_CONTRIBUTION`
  - `COACH`
  - `COMMISSION`
  - `COURT`
- Direction is derived from tag:
  - `MONTHLY_CONTRIBUTION` -> `CREDIT`
  - `COACH`, `COMMISSION`, `COURT` -> `DEBIT`
- Rules are persisted as recurring entries with source `RECURRING_RULE`
- Duplicate active recurring rules are prevented per recurrence target
- Inactive recurring rules are excluded by default and can be included with `include_inactive=true`
- Team ID may be passed in the body or query string on create/update, but mismatches are rejected
- Business rules enforced by tag:
  - `MONTHLY_CONTRIBUTION` requires `athlete_id`
  - `COACH` forbids `athlete_id`
  - `COMMISSION` forbids `athlete_id` and requires `person_name`
  - `COURT` forbids both `athlete_id` and `person_name`
- Amounts are normalized to 2 decimal places and default currency is `BRL`

### Authorization Model

- Access tokens are required on every protected endpoint using `Authorization: Bearer <token>`
- Organization roles:
  - `OWNER`
  - `ADMIN`
  - `MEMBER`
- Team roles:
  - `TEAM_ADMIN`
  - `COACH`
  - `ASSISTANT`
  - `PLAYER`
  - `VIEWER`
- Owners and admins automatically get access to all active teams in the organization
- Team-level permissions are enforced for athlete, coach, finance, and membership operations
- Organization-level permissions are enforced for workspace, member, and team creation operations

### Google Workspace Integration

- Organization workspace provisioning in Google Drive
- Stable folder structure under a root folder named `Volley ERP`
- Organization subfolders created for:
  - `sheets`
  - `images`
  - `exports`
- Drive folders are tagged with app properties for reconciliation
- Workspace IDs are persisted back into the organization record
- Team spreadsheets are stored in the organization `sheets` folder
- Athlete and coach image assets are stored in the organization `images` folder
- Storage ownership is organization-scoped and backed by a stored Google refresh token

### Error Handling

- Central FastAPI exception handlers for auth, workspace, invite, org, and team errors
- Structured API errors for common failure modes such as:
  - `unauthorized`
  - `invalid_token`
  - `token_expired`
  - `forbidden`
  - `organization_not_found`
  - `team_not_found`
  - `invite_not_found`
  - `invite_expired`
  - `invite_already_accepted`
  - `invite_email_mismatch`
  - `storage_owner_connection_missing`
  - `workspace_provisioning_failed`

## API Surface

### Auth

- `GET /auth/google/start`
- `GET /auth/google/callback`
- `POST /auth/google/mobile`
- `POST /security/refresh`
- `GET /security/me`

### Organizations

- `POST /organizations`
- `GET /organizations`
- `GET /organizations/{org_id}`
- `POST /organizations/{org_id}/workspace/ensure`
- `POST /organizations/{org_id}/invites`
- `POST /organizations/invites/accept`
- `GET /organizations/{org_id}/members`
- `DELETE /organizations/{org_id}/members/{user_id}`

### Teams

- `POST /teams`
- `GET /teams`
- `GET /teams/detail`
- `POST /teams/members`
- `GET /teams/members`

### Athletes

- `POST /athletes`
- `PUT /athletes`
- `GET /athletes`
- `GET /athletes/photo/{athlete_id}`

### Coach

- `POST /coach`
- `PUT /coach`
- `GET /coach`
- `GET /coach/photo`

### Monthly Fees

- `GET /monthly_fees`
- `POST /monthly_fees`
- `PUT /monthly_fees/{fee_id}`
- `DELETE /monthly_fees/{fee_id}`

## Data and Storage Model

- API framework: FastAPI
- Dependency injection: `dependency-injector`
- Primary metadata store: Firestore
- OAuth identity provider: Google
- User file workspace: Google Drive
- Team data store: Google Sheets
- Token format: HS256 JWT access and refresh tokens

## Environment Configuration

The repo includes an `.env.example` with the currently expected variables.

### Core App

- `CORS_ALLOW_ORIGINS`
- `CORS_ALLOW_CREDENTIALS`

### Google Credentials

- `GOOGLE_AUTH_MODE`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `GOOGLE_CLOUD_PROJECT`

### Firestore

- `FIRESTORE_DATABASE_ID`
- `FIRESTORE_USERS_COLLECTION`
- `FIRESTORE_GOOGLE_CONNECTIONS_COLLECTION`
- `FIRESTORE_ORGANIZATIONS_COLLECTION`
- `FIRESTORE_USER_ORGANIZATIONS_COLLECTION`

### Google OAuth

- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`
- `GOOGLE_OAUTH_ANDROID_CLIENT_ID`
- `GOOGLE_OAUTH_ANDROID_CLIENT_SECRET`
- `GOOGLE_OAUTH_IOS_CLIENT_ID`
- `GOOGLE_OAUTH_IOS_CLIENT_SECRET`

### Auth and Invite Settings

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
- `TOKEN_ENC_KEY_SECRET_NAME`
- `INVITE_TOKEN_TTL_SECONDS`
- `APP_PUBLIC_BASE_URL`

## Local Development

### Requirements

- Python 3.12+
- Google Cloud credentials for Firestore and Google APIs
- Google OAuth client credentials

### Run

```bash
uvicorn main:app --reload
# or
python main.py --reload
```

### Local Google Auth Setup

```bash
gcloud auth application-default login
```

Set `GOOGLE_AUTH_MODE=adc` for local development.

## Tests

Current automated coverage includes:

- auth workflow
- authorization service
- organization service and controller
- workspace service
- invite service
- team controller and organization team service
- athlete controller
- coach controller and service
- monthly fees controller and service
- Google credential loading

Run tests with:

```bash
.venv/bin/python -m unittest discover -s tests
```

## Current Constraints Visible In Code

- Google Drive and Google Sheets are required for workspace-backed org/team operations
- Organization creation requires an existing Google connection with Drive and Sheets scopes
- Invited users do not provision personal workspaces; storage stays organization-scoped
- Monthly fee endpoints currently manage recurring rule entries, not one-off transactional ledger items
- Coach endpoints currently represent a single coach record per team spreadsheet

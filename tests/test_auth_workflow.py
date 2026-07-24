import json
import unittest
import uuid
from urllib.parse import parse_qs, unquote, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.auth_controller import create_auth_router
from controllers.exception_handlers import register_exception_handlers
from repositories.auth_repository import AuthRepositoryError
from services.security.auth_config import AuthConfig
from services.security.auth_guard import AuthGuard
from services.security.auth_service import AuthService
from services.security.jwt_token_service import JWTTokenService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)
from services.security.state_token_service import StateTokenService


class FakeAuthRepository:
    def __init__(self) -> None:
        self.google_claims = {
            "sub": "google-sub-1",
            "email": "person@example.com",
            "name": "Person Name",
            "aud": "web-client-id",
        }
        self.refresh_token = "google-refresh-token"

    def build_google_authorization_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        scopes: list[str],
        state: str,
    ) -> str:
        return (
            "https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={client_id}&state={state}"
        )

    def exchange_google_code(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict:
        if code == "invalid-grant":
            raise AuthRepositoryError(error="invalid_grant", error_description="Bad code")
        return {
            "access_token": "google-access",
            "refresh_token": self.refresh_token,
            "id_token": "google-id-token",
            "scope": "openid email profile https://www.googleapis.com/auth/drive.file",
        }

    def verify_google_id_token(
        self, *, id_token: str, audience: str | None = None
    ) -> dict:
        if id_token == "invalid-id-token":
            raise AuthRepositoryError(
                error="invalid_id_token", error_description="Invalid ID token"
            )
        claims = dict(self.google_claims)
        if audience and claims.get("aud") != audience:
            raise AuthRepositoryError(
                error="invalid_id_token", error_description="Audience mismatch"
            )
        return claims


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.by_sub = {}
        self.by_id = {}

    def get_by_user_id(self, *, user_id: str):
        user = self.by_id.get(user_id)
        return dict(user) if user else None

    def get_by_google_sub(self, *, google_sub: str):
        user = self.by_sub.get(google_sub)
        return dict(user) if user else None

    def get_by_email(self, *, email: str):
        for user in self.by_id.values():
            if user.get("email") == email:
                return dict(user)
        return None

    def upsert_from_google_identity(self, *, google_sub: str, email: str | None, name: str | None):
        existing = self.by_sub.get(google_sub)
        if existing is None:
            payload = {
                "user_id": str(uuid.uuid4()),
                "google_sub": google_sub,
                "email": email,
                "name": name,
            }
        else:
            payload = {
                **existing,
                "email": email or existing.get("email"),
                "name": name or existing.get("name"),
            }
        self.by_sub[google_sub] = payload
        self.by_id[payload["user_id"]] = payload
        return dict(payload)


class InMemoryGoogleConnectionRepository:
    def __init__(self) -> None:
        self.by_user_id = {}

    def get_by_user_id(self, *, user_id: str):
        connection = self.by_user_id.get(user_id)
        return dict(connection) if connection else None

    def upsert_google_connection(
        self,
        *,
        user_id: str,
        encrypted_refresh_token: str | None,
        scopes: list[str],
    ):
        existing = self.by_user_id.get(user_id)
        payload = {
            "provider": "google",
            "user_id": user_id,
            "encrypted_refresh_token": encrypted_refresh_token
            or (existing or {}).get("encrypted_refresh_token"),
            "scopes": list(scopes),
        }
        self.by_user_id[user_id] = payload
        return dict(payload)


class InMemoryOrganizationRepository:
    def __init__(self) -> None:
        self.user_orgs: dict[str, list[dict]] = {}
        self.org_teams: dict[str, list[dict]] = {}
        self.user_team_pointers: dict[tuple[str, str], list[dict]] = {}

    def list_user_organizations(self, *, user_id: str):
        return list(self.user_orgs.get(user_id, []))

    def list_teams_for_org(self, *, org_id: str):
        return list(self.org_teams.get(org_id, []))

    def list_user_team_pointers(self, *, user_id: str, org_id: str):
        return list(self.user_team_pointers.get((user_id, org_id), []))


def _build_auth_components() -> tuple[
    FastAPI,
    AuthService,
    JWTTokenService,
    InMemoryUserRepository,
    InMemoryOrganizationRepository,
]:
    auth_config = AuthConfig(
        google_oauth_client_id="web-client-id",
        google_oauth_client_secret="web-client-secret",
        google_oauth_redirect_uri="https://api.example.com/auth/google/callback",
        google_oauth_android_client_id="android-client-id",
        google_oauth_android_client_secret="android-client-secret",
        google_oauth_ios_client_id="ios-client-id",
        google_oauth_ios_client_secret="ios-client-secret",
        auth_state_secret="state-secret",
        jwt_access_secret="jwt-access-secret-jwt-access-secret-123",
        jwt_refresh_secret="jwt-refresh-secret-jwt-refresh-secret-123",
        jwt_issuer="volley-erp",
        jwt_audience="volley-erp-client",
        jwt_access_ttl_seconds=600,
        jwt_refresh_ttl_seconds=604800,
        auth_redirect_allowed_origins=["https://app.example.com"],
        auth_redirect_allowed_schemes=["myapp"],
        auth_mobile_allowed_platforms=["android", "ios"],
        auth_mobile_redirect_allowed_android=["com.example.android:/oauth2redirect"],
        auth_mobile_redirect_allowed_ios=["com.example.ios:/oauth2redirect"],
        token_enc_key="test-token-encryption-key",
        token_enc_key_secret_name=None,
        invite_token_ttl_seconds=604800,
        app_public_base_url="https://app.example.com",
    )

    auth_repository = FakeAuthRepository()
    user_repository = InMemoryUserRepository()
    google_connection_repository = InMemoryGoogleConnectionRepository()
    organization_repository = InMemoryOrganizationRepository()

    token_service = JWTTokenService(auth_config=auth_config)
    state_token_service = StateTokenService(secret=auth_config.auth_state_secret)
    refresh_token_encryption_service = RefreshTokenEncryptionService(
        auth_config=auth_config
    )
    auth_service = AuthService(
        auth_config=auth_config,
        auth_repository=auth_repository,
        user_repository=user_repository,
        google_connection_repository=google_connection_repository,
        organization_repository=organization_repository,
        token_service=token_service,
        state_token_service=state_token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    auth_guard = AuthGuard(auth_service=auth_service)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(create_auth_router(auth_service, auth_guard))
    return app, auth_service, token_service, user_repository, organization_repository


def _extract_state(auth_url: str) -> str:
    parsed = urlsplit(auth_url)
    return parse_qs(parsed.query)["state"][0]


class AuthWorkflowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.app,
            self.auth_service,
            self.token_service,
            self.user_repository,
            self.organization_repository,
        ) = _build_auth_components()
        self.client = TestClient(self.app)

    def test_callback_json_mode_returns_user_and_orgs_without_workspace(self):
        self.organization_repository.user_orgs = {}
        start_response = self.client.get("/auth/google/start")
        state = _extract_state(start_response.json()["auth_url"])

        callback_response = self.client.get(
            f"/auth/google/callback?code=valid-code&state={state}"
        )
        body = callback_response.json()

        self.assertEqual(callback_response.status_code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertIn("user_id", body)
        self.assertNotIn("workspace_root_folder_id", body)
        self.assertEqual(body["organizations"], [])

    def test_callback_redirect_mode_payload_contains_user_id_and_tokens(self):
        start_response = self.client.get(
            "/auth/google/start?redirect_uri=https://app.example.com/callback"
        )
        state = _extract_state(start_response.json()["auth_url"])
        callback_response = self.client.get(
            f"/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        self.assertEqual(callback_response.status_code, 302)
        location = callback_response.headers["Location"]
        payload_json = unquote(urlsplit(location).fragment.split("payload=", maxsplit=1)[1])
        payload = json.loads(payload_json)
        self.assertIn("user_id", payload)
        self.assertIn("access_token", payload)
        self.assertIn("refresh_token", payload)

    def test_callback_accepts_state_issued_by_different_service_instance(self):
        start_response = self.client.get(
            "/auth/google/start?redirect_uri=https://app.example.com/callback"
        )
        state = _extract_state(start_response.json()["auth_url"])

        (
            other_app,
            _other_auth_service,
            _other_token_service,
            _other_user_repository,
            _other_organization_repository,
        ) = _build_auth_components()
        other_client = TestClient(other_app)

        callback_response = other_client.get(
            f"/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        self.assertEqual(callback_response.status_code, 302)

    def test_security_me_returns_org_visibility(self):
        # Login once to create user and get app token.
        state = _extract_state(self.client.get("/auth/google/start").json()["auth_url"])
        callback = self.client.get(f"/auth/google/callback?code=valid-code&state={state}")
        payload = callback.json()
        user_id = payload["user_id"]

        self.organization_repository.user_orgs[user_id] = [
            {
                "org_id": "org-1",
                "org_name": "Org One",
                "org_role": "MEMBER",
                "status": "active",
            }
        ]
        self.organization_repository.user_team_pointers[(user_id, "org-1")] = [
            {
                "team_id": "team-1",
                "team_name": "Team One",
                "team_role": "COACH",
                "status": "active",
            }
        ]

        me_response = self.client.get(
            "/security/me",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        me = me_response.json()

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me["user_id"], user_id)
        self.assertEqual(me["organizations"][0]["org_id"], "org-1")
        self.assertEqual(me["organizations"][0]["teams"][0]["team_id"], "team-1")

    def test_security_me_for_org_admin_includes_all_active_org_teams(self):
        state = _extract_state(self.client.get("/auth/google/start").json()["auth_url"])
        callback = self.client.get(f"/auth/google/callback?code=valid-code&state={state}")
        payload = callback.json()
        user_id = payload["user_id"]

        self.organization_repository.user_orgs[user_id] = [
            {
                "org_id": "org-1",
                "org_name": "Org One",
                "org_role": "ADMIN",
                "status": "active",
            }
        ]
        self.organization_repository.org_teams["org-1"] = [
            {"team_id": "team-a", "name": "Team A", "status": "active"},
            {"team_id": "team-b", "name": "Team B", "status": "active"},
            {"team_id": "team-c", "name": "Team C", "status": "inactive"},
        ]

        me_response = self.client.get(
            "/security/me",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        me = me_response.json()

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me["organizations"][0]["org_id"], "org-1")
        self.assertEqual(
            {team["team_id"] for team in me["organizations"][0]["teams"]},
            {"team-a", "team-b"},
        )
        self.assertEqual(
            {team["team_role"] for team in me["organizations"][0]["teams"]},
            {"ORG_ADMIN"},
        )

    def test_refresh_issues_new_pair_without_workspace_side_effects(self):
        state = _extract_state(self.client.get("/auth/google/start").json()["auth_url"])
        callback = self.client.get(f"/auth/google/callback?code=valid-code&state={state}")
        refresh_token = callback.json()["refresh_token"]

        refresh_response = self.client.post(
            "/security/refresh",
            json={"refresh_token": refresh_token},
        )
        refreshed = refresh_response.json()

        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access_token", refreshed)
        self.assertIn("refresh_token", refreshed)
        self.assertEqual(refreshed["token_type"], "Bearer")


if __name__ == "__main__":
    unittest.main()

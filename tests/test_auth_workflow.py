import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlsplit

import jwt
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


class InMemoryCustomerRepository:
    def __init__(self) -> None:
        self.by_sub = {}
        self.by_id = {}

    def get_by_google_sub(self, *, google_sub: str):
        customer = self.by_sub.get(google_sub)
        return dict(customer) if customer else None

    def get_by_customer_id(self, *, customer_id: str):
        customer = self.by_id.get(customer_id)
        return dict(customer) if customer else None

    def upsert_by_google_sub(self, *, google_sub: str, email: str | None, refresh_token_enc: str):
        existing = self.by_sub.get(google_sub)
        if existing is None:
            customer = {
                "customer_id": str(uuid.uuid4()),
                "google_sub": google_sub,
                "email": email,
                "refresh_token_enc": refresh_token_enc,
                "doc_id": None,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        else:
            customer = {
                **existing,
                "email": email or existing.get("email"),
                "refresh_token_enc": refresh_token_enc,
                "updated_at": "2026-01-01T00:01:00Z",
            }
        self.by_sub[google_sub] = customer
        self.by_id[customer["customer_id"]] = customer
        return dict(customer)

    def update_doc_id(self, *, customer_id: str, doc_id: str | None):
        customer = dict(self.by_id[customer_id])
        customer["doc_id"] = doc_id
        self.by_id[customer_id] = customer
        self.by_sub[customer["google_sub"]] = customer
        return dict(customer)


def _build_auth_components(
    *,
    access_ttl_seconds: int = 600,
    refresh_ttl_seconds: int = 604800,
) -> tuple[FastAPI, AuthService, JWTTokenService, InMemoryCustomerRepository, AuthConfig]:
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
        jwt_access_ttl_seconds=access_ttl_seconds,
        jwt_refresh_ttl_seconds=refresh_ttl_seconds,
        auth_redirect_allowed_origins=["https://app.example.com"],
        auth_redirect_allowed_schemes=["myapp"],
        auth_mobile_allowed_platforms=["android", "ios"],
        auth_mobile_redirect_allowed_android=["com.example.android:/oauth2redirect"],
        auth_mobile_redirect_allowed_ios=["com.example.ios:/oauth2redirect"],
        token_enc_key="test-token-encryption-key",
        token_enc_key_secret_name=None,
    )

    auth_repository = FakeAuthRepository()
    customer_repository = InMemoryCustomerRepository()
    token_service = JWTTokenService(auth_config=auth_config)
    state_token_service = StateTokenService(secret=auth_config.auth_state_secret)
    refresh_token_encryption_service = RefreshTokenEncryptionService(
        auth_config=auth_config
    )
    auth_service = AuthService(
        auth_config=auth_config,
        auth_repository=auth_repository,
        customer_repository=customer_repository,
        token_service=token_service,
        state_token_service=state_token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    auth_guard = AuthGuard(auth_service=auth_service)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(create_auth_router(auth_service, auth_guard))
    return app, auth_service, token_service, customer_repository, auth_config


def _extract_state(auth_url: str) -> str:
    parsed = urlsplit(auth_url)
    return parse_qs(parsed.query)["state"][0]


class AuthWorkflowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.app,
            self.auth_service,
            self.token_service,
            self.customer_repository,
            self.auth_config,
        ) = _build_auth_components()
        self.client = TestClient(self.app)

    def _create_customer_and_tokens(self) -> dict:
        encrypted_refresh = RefreshTokenEncryptionService(
            auth_config=self.auth_config
        ).encrypt("google-refresh-token")
        customer = self.customer_repository.upsert_by_google_sub(
            google_sub="google-sub-manual",
            email="manual@example.com",
            refresh_token_enc=encrypted_refresh,
        )
        return {"customer": customer, "tokens": self.token_service.issue_token_pair(customer)}

    def test_start_native_allowlisted_redirect(self):
        response = self.client.get("/auth/google/start?redirect_uri=myapp://oauth/callback")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["callback_mode"], "redirect")
        self.assertEqual(body["redirect_uri"], "myapp://oauth/callback")
        self.assertIn("auth_url", body)

    def test_start_native_non_allowlisted_redirect(self):
        response = self.client.get(
            "/auth/google/start?redirect_uri=notallowed://oauth/callback"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_redirect_uri")

    def test_callback_success_redirect_for_native_deep_link(self):
        start_response = self.client.get(
            "/auth/google/start?redirect_uri=myapp://oauth/callback"
        )
        state = _extract_state(start_response.json()["auth_url"])

        callback_response = self.client.get(
            f"/auth/google/callback?code=valid-code&state={state}",
            follow_redirects=False,
        )

        self.assertEqual(callback_response.status_code, 302)
        location = callback_response.headers["Location"]
        self.assertTrue(location.startswith("myapp://oauth/callback"))
        query_params = parse_qs(urlsplit(location).query)
        self.assertIn("access_token", query_params)
        self.assertEqual(query_params["token_type"][0], "Bearer")
        self.assertIn("refresh_token", query_params)

    def test_callback_error_redirect_includes_error_and_error_description(self):
        start_response = self.client.get(
            "/auth/google/start?redirect_uri=myapp://oauth/callback"
        )
        state = _extract_state(start_response.json()["auth_url"])

        callback_response = self.client.get(
            f"/auth/google/callback?state={state}&error=access_denied"
            "&error_description=User+denied",
            follow_redirects=False,
        )

        self.assertEqual(callback_response.status_code, 302)
        query_params = parse_qs(urlsplit(callback_response.headers["Location"]).query)
        self.assertEqual(query_params["error"][0], "access_denied")
        self.assertEqual(query_params["error_description"][0], "User denied")

    def test_callback_with_no_redirect_uri_state_returns_json_mode(self):
        start_response = self.client.get("/auth/google/start")
        state = _extract_state(start_response.json()["auth_url"])

        callback_response = self.client.get(
            f"/auth/google/callback?code=valid-code&state={state}"
        )

        self.assertEqual(callback_response.status_code, 200)
        body = callback_response.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("access_token", body)
        self.assertEqual(body["token_type"], "Bearer")
        self.assertIn("refresh_token", body)
        self.assertIn("expires_in", body)

    def test_callback_with_web_redirect_uri_uses_fragment_payload_redirect(self):
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
        parsed = urlsplit(location)
        self.assertEqual(
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
            "https://app.example.com/callback",
        )
        self.assertTrue(parsed.fragment.startswith("payload="))
        payload_json = unquote(parsed.fragment.split("payload=", maxsplit=1)[1])
        payload = json.loads(payload_json)
        self.assertIn("access_token", payload)
        self.assertEqual(payload["token_type"], "Bearer")
        self.assertIn("refresh_token", payload)

    def test_state_token_one_time_use(self):
        start_response = self.client.get("/auth/google/start")
        state = _extract_state(start_response.json()["auth_url"])

        first_callback = self.client.get(f"/auth/google/callback?code=valid-code&state={state}")
        second_callback = self.client.get(
            f"/auth/google/callback?code=valid-code&state={state}"
        )

        self.assertEqual(first_callback.status_code, 200)
        self.assertEqual(second_callback.status_code, 400)
        self.assertEqual(second_callback.json()["error"], "invalid_state")

    def test_security_refresh_and_me_happy_path(self):
        created = self._create_customer_and_tokens()
        access_token = created["tokens"]["access_token"]
        refresh_token = created["tokens"]["refresh_token"]
        customer = created["customer"]

        me_response = self.client.get(
            "/security/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        refresh_response = self.client.post(
            "/security/refresh",
            json={"refresh_token": refresh_token},
        )

        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["customer_id"], customer["customer_id"])
        self.assertEqual(me_response.json()["google_sub"], customer["google_sub"])
        self.assertEqual(me_response.json()["email"], customer["email"])
        self.assertEqual(me_response.json()["doc_id"], customer["doc_id"])

        self.assertEqual(refresh_response.status_code, 200)
        refreshed = refresh_response.json()
        self.assertIn("access_token", refreshed)
        self.assertIn("refresh_token", refreshed)
        self.assertEqual(refreshed["token_type"], "Bearer")
        self.assertIn("expires_in", refreshed)

    def test_security_me_and_refresh_invalid_and_expired_paths(self):
        created = self._create_customer_and_tokens()
        access_token = created["tokens"]["access_token"]

        missing_me = self.client.get("/security/me")
        invalid_me = self.client.get(
            "/security/me",
            headers={"Authorization": "Bearer not-a-token"},
        )
        self.assertEqual(missing_me.status_code, 401)
        self.assertEqual(missing_me.json()["error"], "unauthorized")
        self.assertEqual(missing_me.headers.get("WWW-Authenticate"), "Bearer")
        self.assertEqual(invalid_me.status_code, 401)
        self.assertEqual(invalid_me.json()["error"], "invalid_token")

        refresh_with_access = self.client.post(
            "/security/refresh",
            json={"refresh_token": access_token},
        )
        self.assertEqual(refresh_with_access.status_code, 401)
        self.assertEqual(refresh_with_access.json()["error"], "invalid_token")

        now = datetime.now(timezone.utc)
        expired_access = jwt.encode(
            {
                "iss": self.auth_config.jwt_issuer,
                "aud": self.auth_config.jwt_audience,
                "sub": created["customer"]["customer_id"],
                "type": "access",
                "iat": int((now - timedelta(minutes=10)).timestamp()),
                "nbf": int((now - timedelta(minutes=10)).timestamp()),
                "exp": int((now - timedelta(minutes=5)).timestamp()),
                "jti": str(uuid.uuid4()),
            },
            self.auth_config.jwt_access_secret,
            algorithm="HS256",
        )
        expired_me = self.client.get(
            "/security/me",
            headers={"Authorization": f"Bearer {expired_access}"},
        )
        self.assertEqual(expired_me.status_code, 401)
        self.assertEqual(expired_me.json()["error"], "token_expired")

        expired_refresh = jwt.encode(
            {
                "iss": self.auth_config.jwt_issuer,
                "aud": self.auth_config.jwt_audience,
                "sub": created["customer"]["customer_id"],
                "type": "refresh",
                "iat": int((now - timedelta(days=8)).timestamp()),
                "nbf": int((now - timedelta(days=8)).timestamp()),
                "exp": int((now - timedelta(days=7)).timestamp()),
                "jti": str(uuid.uuid4()),
            },
            self.auth_config.jwt_refresh_secret,
            algorithm="HS256",
        )
        refresh_expired = self.client.post(
            "/security/refresh",
            json={"refresh_token": expired_refresh},
        )
        self.assertEqual(refresh_expired.status_code, 401)
        self.assertEqual(refresh_expired.json()["error"], "token_expired")


if __name__ == "__main__":
    unittest.main()

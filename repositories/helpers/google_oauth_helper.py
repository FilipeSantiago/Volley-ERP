import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class GoogleOAuthHelperError(Exception):
    def __init__(self, error: str, error_description: str | None = None) -> None:
        self.error = error
        self.error_description = error_description or ""
        super().__init__(self.error_description or self.error)


class GoogleOAuthHelper:
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def build_authorization_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        scopes: list[str],
        state: str,
    ) -> str:
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
            params
        )

    def exchange_code(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            payload["code_verifier"] = code_verifier

        encoded_data = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            self.TOKEN_URL,
            data=encoded_data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8")
            error_payload = self._parse_error_payload(error_body)
            raise GoogleOAuthHelperError(
                error=error_payload.get("error", "oauth_exchange_failed"),
                error_description=error_payload.get("error_description")
                or "OAuth code exchange failed.",
            ) from error
        except urllib.error.URLError as error:
            raise GoogleOAuthHelperError(
                error="oauth_exchange_failed",
                error_description="OAuth code exchange failed.",
            ) from error

        token_payload = json.loads(response_body)
        if "error" in token_payload:
            raise GoogleOAuthHelperError(
                error=token_payload.get("error", "oauth_exchange_failed"),
                error_description=token_payload.get("error_description"),
            )
        return token_payload

    def verify_id_token(
        self, *, id_token: str, audience: str | None = None
    ) -> dict[str, Any]:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import id_token as google_id_token
        except ModuleNotFoundError as error:
            raise GoogleOAuthHelperError(
                error="invalid_id_token",
                error_description="google-auth dependencies are not installed.",
            ) from error

        try:
            return google_id_token.verify_oauth2_token(id_token, Request(), audience)
        except ValueError as error:
            raise GoogleOAuthHelperError(
                error="invalid_id_token",
                error_description="ID token validation failed.",
            ) from error

    @staticmethod
    def _parse_error_payload(raw_body: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError:
            return {}
        if isinstance(payload, dict):
            return payload
        return {}

import json
import re
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from repositories.auth_repository import AuthRepository, AuthRepositoryError
from repositories.customer_repository import CustomerRepository
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import (
    DisallowedPlatformClientMismatchError,
    InvalidCodeError,
    InvalidCodeVerifierError,
    InvalidRedirectURIError,
    InvalidStateError,
    InvalidTokenError,
    OAuthConfigurationError,
    OAuthProviderError,
    TokenExpiredError,
)
from services.security.jwt_token_service import JWTTokenService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)
from services.security.state_token_service import StateTokenService

PKCE_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


class AuthService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        auth_repository: AuthRepository,
        customer_repository: CustomerRepository,
        token_service: JWTTokenService,
        state_token_service: StateTokenService,
        refresh_token_encryption_service: RefreshTokenEncryptionService,
    ) -> None:
        self._auth_config = auth_config
        self._auth_repository = auth_repository
        self._customer_repository = customer_repository
        self._token_service = token_service
        self._state_token_service = state_token_service
        self._refresh_token_encryption_service = refresh_token_encryption_service

    def start_google_auth(
        self, *, redirect_uri: str | None, platform: str | None = None
    ) -> dict[str, Any]:
        self._ensure_web_oauth_configured()

        callback_mode = "json"
        normalized_redirect_uri = None
        if redirect_uri:
            normalized_redirect_uri = self._validate_and_normalize_redirect_uri(
                redirect_uri
            )
            callback_mode = "redirect"

        state = self._state_token_service.issue_state_token(
            callback_mode=callback_mode,
            redirect_uri=normalized_redirect_uri,
            platform=platform,
        )
        auth_url = self._auth_repository.build_google_authorization_url(
            client_id=self._auth_config.google_oauth_client_id,
            redirect_uri=self._auth_config.google_oauth_redirect_uri,
            scopes=GOOGLE_SCOPES,
            state=state,
        )

        response: dict[str, Any] = {
            "auth_url": auth_url,
            "callback_mode": callback_mode,
        }
        if normalized_redirect_uri:
            response["redirect_uri"] = normalized_redirect_uri
        return response

    def handle_google_callback(self, *, params: dict[str, str | None]) -> dict[str, Any]:
        state_token = params.get("state")
        if not isinstance(state_token, str) or not state_token:
            raise InvalidStateError("invalid_state")

        state_payload = self._state_token_service.consume_state_token(state_token)
        callback_mode = state_payload.get("callback_mode")
        redirect_uri = state_payload.get("redirect_uri")
        if callback_mode not in {"json", "redirect"}:
            raise InvalidStateError("invalid_state")

        if redirect_uri:
            self._validate_and_normalize_redirect_uri(redirect_uri)

        provider_error = params.get("error")
        if provider_error:
            provider_error_description = params.get("error_description")
            if callback_mode == "redirect" and redirect_uri:
                redirect_url = self._build_redirect_with_query_params(
                    redirect_uri,
                    {
                        "error": provider_error,
                        "error_description": provider_error_description or "",
                    },
                )
                return {"mode": "redirect", "redirect_url": redirect_url}
            raise OAuthProviderError(
                error=provider_error,
                error_description=provider_error_description,
            )

        authorization_code = params.get("code")
        if not isinstance(authorization_code, str) or not authorization_code:
            raise InvalidCodeError("invalid_code")

        token_payload = self._exchange_web_code(authorization_code=authorization_code)
        id_token = token_payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise InvalidCodeError("invalid_code")

        try:
            google_claims = self._auth_repository.verify_google_id_token(
                id_token=id_token,
                audience=self._auth_config.google_oauth_client_id,
            )
        except AuthRepositoryError as error:
            raise OAuthProviderError(
                error=error.error,
                error_description=error.error_description,
            ) from error
        customer = self._upsert_customer_from_google_claims(
            google_claims=google_claims,
            refresh_token=token_payload.get("refresh_token"),
        )
        token_pair = self._token_service.issue_token_pair(customer)

        json_payload = {
            "status": "ok",
            "customer_id": customer["customer_id"],
            "google_sub": customer["google_sub"],
            "email": customer.get("email"),
            "doc_id": customer.get("doc_id"),
            **token_pair,
        }

        if callback_mode == "redirect" and redirect_uri:
            success_redirect_url = self._build_success_redirect_url(
                redirect_uri=redirect_uri,
                token_pair=token_pair,
            )
            return {"mode": "redirect", "redirect_url": success_redirect_url}

        return {"mode": "json", "status_code": 200, "payload": json_payload}

    def exchange_google_mobile_code(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_mobile_oauth_configured()

        authorization_code = payload.get("authorization_code")
        code_verifier = payload.get("code_verifier")
        redirect_uri = payload.get("redirect_uri")
        platform = payload.get("platform")

        if not isinstance(authorization_code, str) or not authorization_code.strip():
            raise InvalidCodeError("invalid_code")
        if not isinstance(code_verifier, str) or not PKCE_VERIFIER_PATTERN.match(
            code_verifier
        ):
            raise InvalidCodeVerifierError("invalid_code_verifier")
        if not isinstance(redirect_uri, str) or not redirect_uri.strip():
            raise InvalidRedirectURIError("invalid_redirect_uri")
        if not isinstance(platform, str):
            raise DisallowedPlatformClientMismatchError(
                "disallowed_platform_client_mismatch"
            )

        normalized_platform = platform.strip().lower()
        normalized_redirect_uri = self._validate_mobile_redirect_uri(
            platform=normalized_platform,
            redirect_uri=redirect_uri,
        )
        client_id, client_secret = self._resolve_mobile_client_credentials(
            platform=normalized_platform
        )

        try:
            token_payload = self._auth_repository.exchange_google_code(
                client_id=client_id,
                client_secret=client_secret,
                code=authorization_code.strip(),
                redirect_uri=normalized_redirect_uri,
                code_verifier=code_verifier,
            )
        except AuthRepositoryError as error:
            if error.error == "invalid_grant":
                raise InvalidCodeError("invalid_code") from error
            raise OAuthProviderError(
                error=error.error,
                error_description=error.error_description,
            ) from error

        id_token = token_payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise InvalidCodeError("invalid_code")

        try:
            google_claims = self._auth_repository.verify_google_id_token(
                id_token=id_token,
                audience=None,
            )
        except AuthRepositoryError as error:
            raise OAuthProviderError(
                error=error.error,
                error_description=error.error_description,
            ) from error
        if google_claims.get("aud") != client_id:
            raise DisallowedPlatformClientMismatchError(
                "disallowed_platform_client_mismatch"
            )

        customer = self._upsert_customer_from_google_claims(
            google_claims=google_claims,
            refresh_token=token_payload.get("refresh_token"),
        )
        token_pair = self._token_service.issue_token_pair(customer)
        return {
            "status": "ok",
            "customer_id": customer["customer_id"],
            "google_sub": customer["google_sub"],
            "email": customer.get("email"),
            "doc_id": customer.get("doc_id"),
            **token_pair,
        }

    def refresh_token_pair(self, *, refresh_token: str) -> dict[str, Any]:
        claims = self._token_service.validate_refresh_token(refresh_token)
        customer_id = claims.get("sub")
        if not isinstance(customer_id, str):
            raise InvalidTokenError("invalid_token")

        customer = self._customer_repository.get_by_customer_id(customer_id=customer_id)
        if customer is None:
            raise InvalidTokenError("invalid_token")

        return self._token_service.issue_token_pair(customer)

    def get_me(self, *, access_token: str) -> dict[str, Any]:
        claims = self._token_service.validate_access_token(access_token)
        return {
            "customer_id": claims.get("sub"),
            "google_sub": claims.get("google_sub"),
            "email": claims.get("email"),
            "doc_id": claims.get("doc_id"),
        }

    def validate_access_token(self, *, access_token: str) -> dict[str, Any]:
        return self._token_service.validate_access_token(access_token)

    def issue_token_pair_for_customer(self, *, customer: dict[str, Any]) -> dict[str, Any]:
        return self._token_service.issue_token_pair(customer)

    def _exchange_web_code(self, *, authorization_code: str) -> dict[str, Any]:
        try:
            return self._auth_repository.exchange_google_code(
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                code=authorization_code,
                redirect_uri=self._auth_config.google_oauth_redirect_uri,
            )
        except AuthRepositoryError as error:
            if error.error == "invalid_grant":
                raise InvalidCodeError("invalid_code") from error
            raise OAuthProviderError(
                error=error.error,
                error_description=error.error_description,
            ) from error

    def _upsert_customer_from_google_claims(
        self, *, google_claims: dict[str, Any], refresh_token: Any
    ) -> dict[str, Any]:
        google_sub = google_claims.get("sub")
        if not isinstance(google_sub, str) or not google_sub:
            raise OAuthProviderError(
                error="invalid_id_token",
                error_description="Google subject was not provided by ID token.",
            )
        email = google_claims.get("email")
        if email is not None and not isinstance(email, str):
            email = None

        existing_customer = self._customer_repository.get_by_google_sub(
            google_sub=google_sub
        )
        if isinstance(refresh_token, str) and refresh_token:
            refresh_token_enc = self._refresh_token_encryption_service.encrypt(
                refresh_token
            )
        elif existing_customer and existing_customer.get("refresh_token_enc"):
            refresh_token_enc = existing_customer["refresh_token_enc"]
        else:
            raise OAuthProviderError(
                error="invalid_grant",
                error_description="OAuth provider did not return a refresh token.",
            )

        return self._customer_repository.upsert_by_google_sub(
            google_sub=google_sub,
            email=email,
            refresh_token_enc=refresh_token_enc,
        )

    def _validate_and_normalize_redirect_uri(self, redirect_uri: str) -> str:
        normalized = redirect_uri.strip()
        parsed = urlsplit(normalized)
        if not parsed.scheme:
            raise InvalidRedirectURIError("invalid_redirect_uri")

        scheme = parsed.scheme.lower()
        if scheme in {"http", "https"}:
            origin = f"{scheme}://{parsed.netloc.lower()}"
            allowed_origins = {
                item.lower().rstrip("/")
                for item in self._auth_config.auth_redirect_allowed_origins
            }
            if origin.rstrip("/") not in allowed_origins:
                raise InvalidRedirectURIError("invalid_redirect_uri")
            return urlunsplit(
                (
                    scheme,
                    parsed.netloc,
                    parsed.path or "",
                    parsed.query,
                    "",
                )
            )

        allowed_schemes = {
            item.lower() for item in self._auth_config.auth_redirect_allowed_schemes
        }
        if scheme not in allowed_schemes:
            raise InvalidRedirectURIError("invalid_redirect_uri")
        return urlunsplit(parsed)

    def _validate_mobile_redirect_uri(self, *, platform: str, redirect_uri: str) -> str:
        allowed_platforms = {
            item.lower() for item in self._auth_config.auth_mobile_allowed_platforms
        }
        if platform not in allowed_platforms:
            raise DisallowedPlatformClientMismatchError(
                "disallowed_platform_client_mismatch"
            )

        normalized_redirect_uri = redirect_uri.strip()
        if not normalized_redirect_uri:
            raise InvalidRedirectURIError("invalid_redirect_uri")

        if platform == "android":
            allowed_redirects = {
                value.strip()
                for value in self._auth_config.auth_mobile_redirect_allowed_android
                if value.strip()
            }
        else:
            allowed_redirects = {
                value.strip()
                for value in self._auth_config.auth_mobile_redirect_allowed_ios
                if value.strip()
            }

        if normalized_redirect_uri not in allowed_redirects:
            raise InvalidRedirectURIError("invalid_redirect_uri")
        return normalized_redirect_uri

    def _resolve_mobile_client_credentials(self, *, platform: str) -> tuple[str, str]:
        if platform == "android":
            client_id = self._auth_config.google_oauth_android_client_id
            client_secret = self._auth_config.google_oauth_android_client_secret
        elif platform == "ios":
            client_id = self._auth_config.google_oauth_ios_client_id
            client_secret = self._auth_config.google_oauth_ios_client_secret
        else:
            raise DisallowedPlatformClientMismatchError(
                "disallowed_platform_client_mismatch"
            )

        if not client_id or not client_secret:
            raise OAuthConfigurationError("Mobile OAuth client is not configured.")
        return client_id, client_secret

    def _build_success_redirect_url(
        self, *, redirect_uri: str, token_pair: dict[str, Any]
    ) -> str:
        parsed = urlsplit(redirect_uri)
        payload = {
            "access_token": token_pair["access_token"],
            "token_type": token_pair["token_type"],
            "refresh_token": token_pair["refresh_token"],
        }

        if parsed.scheme.lower() in {"http", "https"}:
            payload_json = json.dumps(payload, separators=(",", ":"))
            encoded_payload = quote(payload_json, safe="")
            fragment_value = f"payload={encoded_payload}"
            if parsed.fragment:
                fragment_value = f"{parsed.fragment}&{fragment_value}"
            return urlunsplit(
                (
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.query,
                    fragment_value,
                )
            )

        return self._build_redirect_with_query_params(redirect_uri, payload)

    @staticmethod
    def _build_redirect_with_query_params(
        redirect_uri: str, extra_params: dict[str, str]
    ) -> str:
        parsed = urlsplit(redirect_uri)
        query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_params.update(extra_params)
        query_string = urlencode(query_params)
        return urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, query_string, parsed.fragment)
        )

    def _ensure_web_oauth_configured(self) -> None:
        if (
            not self._auth_config.google_oauth_client_id
            or not self._auth_config.google_oauth_client_secret
            or not self._auth_config.google_oauth_redirect_uri
        ):
            raise OAuthConfigurationError("Google web OAuth configuration is missing.")

    def _ensure_mobile_oauth_configured(self) -> None:
        if (
            not self._auth_config.google_oauth_android_client_id
            and not self._auth_config.google_oauth_ios_client_id
        ):
            raise OAuthConfigurationError("Google mobile OAuth configuration is missing.")


def map_token_validation_error(error: Exception) -> str:
    if isinstance(error, TokenExpiredError):
        return "token_expired"
    if isinstance(error, InvalidTokenError):
        return "invalid_token"
    return "invalid_token"

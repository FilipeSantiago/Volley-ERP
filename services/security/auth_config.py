import os
from dataclasses import dataclass


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class AuthConfig:
    google_oauth_client_id: str
    google_oauth_client_secret: str
    google_oauth_redirect_uri: str
    google_oauth_android_client_id: str | None
    google_oauth_android_client_secret: str | None
    google_oauth_ios_client_id: str | None
    google_oauth_ios_client_secret: str | None
    auth_state_secret: str
    jwt_access_secret: str
    jwt_refresh_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_access_ttl_seconds: int
    jwt_refresh_ttl_seconds: int
    auth_redirect_allowed_origins: list[str]
    auth_redirect_allowed_schemes: list[str]
    auth_mobile_allowed_platforms: list[str]
    auth_mobile_redirect_allowed_android: list[str]
    auth_mobile_redirect_allowed_ios: list[str]
    token_enc_key: str | None
    token_enc_key_secret_name: str | None
    invite_token_ttl_seconds: int
    app_public_base_url: str

    @staticmethod
    def from_env() -> "AuthConfig":
        return AuthConfig(
            google_oauth_client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            google_oauth_client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            google_oauth_redirect_uri=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", ""),
            google_oauth_android_client_id=os.getenv("GOOGLE_OAUTH_ANDROID_CLIENT_ID"),
            google_oauth_android_client_secret=os.getenv(
                "GOOGLE_OAUTH_ANDROID_CLIENT_SECRET"
            ),
            google_oauth_ios_client_id=os.getenv("GOOGLE_OAUTH_IOS_CLIENT_ID"),
            google_oauth_ios_client_secret=os.getenv("GOOGLE_OAUTH_IOS_CLIENT_SECRET"),
            auth_state_secret=os.getenv(
                "AUTH_STATE_SECRET",
                "dev-auth-state-secret-dev-auth-state-secret",
            ),
            jwt_access_secret=os.getenv(
                "JWT_ACCESS_SECRET",
                "dev-jwt-access-secret-dev-jwt-access-secret",
            ),
            jwt_refresh_secret=os.getenv(
                "JWT_REFRESH_SECRET",
                "dev-jwt-refresh-secret-dev-jwt-refresh-secret",
            ),
            jwt_issuer=os.getenv("JWT_ISSUER", "volley-erp"),
            jwt_audience=os.getenv("JWT_AUDIENCE", "volley-erp-client"),
            jwt_access_ttl_seconds=int(os.getenv("JWT_ACCESS_TTL_SECONDS", "600")),
            jwt_refresh_ttl_seconds=int(
                os.getenv("JWT_REFRESH_TTL_SECONDS", "604800")
            ),
            auth_redirect_allowed_origins=_parse_csv(
                os.getenv("AUTH_REDIRECT_ALLOWED_ORIGINS")
            ),
            auth_redirect_allowed_schemes=_parse_csv(
                os.getenv("AUTH_REDIRECT_ALLOWED_SCHEMES")
            ),
            auth_mobile_allowed_platforms=_parse_csv(
                os.getenv("AUTH_MOBILE_ALLOWED_PLATFORMS", "android,ios")
            ),
            auth_mobile_redirect_allowed_android=_parse_csv(
                os.getenv("AUTH_MOBILE_REDIRECT_ALLOWED_ANDROID")
            ),
            auth_mobile_redirect_allowed_ios=_parse_csv(
                os.getenv("AUTH_MOBILE_REDIRECT_ALLOWED_IOS")
            ),
            token_enc_key=os.getenv("TOKEN_ENC_KEY", "dev-token-enc-key"),
            token_enc_key_secret_name=os.getenv("TOKEN_ENC_KEY_SECRET_NAME"),
            invite_token_ttl_seconds=int(os.getenv("INVITE_TOKEN_TTL_SECONDS", "604800")),
            app_public_base_url=os.getenv("APP_PUBLIC_BASE_URL", "http://localhost:3000"),
        )

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError as PyJWTInvalidTokenError

from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import InvalidTokenError, TokenExpiredError


class JWTTokenService:
    def __init__(self, *, auth_config: AuthConfig) -> None:
        self._auth_config = auth_config

    def issue_token_pair(self, customer: dict[str, Any]) -> dict[str, Any]:
        access_token = self._issue_token(
            customer=customer,
            token_type="access",
            ttl_seconds=self._auth_config.jwt_access_ttl_seconds,
            secret=self._auth_config.jwt_access_secret,
        )
        refresh_token = self._issue_token(
            customer=customer,
            token_type="refresh",
            ttl_seconds=self._auth_config.jwt_refresh_ttl_seconds,
            secret=self._auth_config.jwt_refresh_secret,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self._auth_config.jwt_access_ttl_seconds,
        }

    def validate_access_token(self, token: str) -> dict[str, Any]:
        return self._validate_token(
            token=token,
            expected_type="access",
            secret=self._auth_config.jwt_access_secret,
        )

    def validate_refresh_token(self, token: str) -> dict[str, Any]:
        return self._validate_token(
            token=token,
            expected_type="refresh",
            secret=self._auth_config.jwt_refresh_secret,
        )

    def _issue_token(
        self,
        *,
        customer: dict[str, Any],
        token_type: str,
        ttl_seconds: int,
        secret: str,
    ) -> str:
        now = datetime.now(timezone.utc)
        issued_at = int(now.timestamp())
        expires_at = int((now + timedelta(seconds=ttl_seconds)).timestamp())
        claims: dict[str, Any] = {
            "iss": self._auth_config.jwt_issuer,
            "aud": self._auth_config.jwt_audience,
            "sub": customer["customer_id"],
            "type": token_type,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": expires_at,
            "jti": str(uuid.uuid4()),
        }

        if customer.get("email"):
            claims["email"] = customer["email"]
        if customer.get("google_sub"):
            claims["google_sub"] = customer["google_sub"]
        if customer.get("doc_id"):
            claims["doc_id"] = customer["doc_id"]

        return jwt.encode(claims, secret, algorithm="HS256")

    def _validate_token(
        self, *, token: str, expected_type: str, secret: str
    ) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=self._auth_config.jwt_audience,
                issuer=self._auth_config.jwt_issuer,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "type",
                        "iat",
                        "nbf",
                        "exp",
                        "jti",
                    ]
                },
            )
        except ExpiredSignatureError as error:
            raise TokenExpiredError("Token expired.") from error
        except PyJWTInvalidTokenError as error:
            raise InvalidTokenError("Invalid token.") from error

        if claims.get("type") != expected_type:
            raise InvalidTokenError("Invalid token type.")

        return claims

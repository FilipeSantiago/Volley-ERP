from typing import Any

from services.security.auth_exceptions import (
    InvalidTokenError,
    UnauthorizedError,
)
from services.security.auth_service import AuthService


class AuthGuard:
    def __init__(self, *, auth_service: AuthService) -> None:
        self._auth_service = auth_service

    def require_access_token(self, *, authorization_header: str | None) -> dict[str, Any]:
        if not authorization_header:
            raise UnauthorizedError("unauthorized")

        prefix = "Bearer "
        if not authorization_header.startswith(prefix):
            raise InvalidTokenError("invalid_token")

        token = authorization_header[len(prefix) :].strip()
        if not token:
            raise UnauthorizedError("unauthorized")

        return self._auth_service.validate_access_token(access_token=token)

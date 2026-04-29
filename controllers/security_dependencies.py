from typing import Any

from fastapi import Header

from services.security.auth_guard import AuthGuard


def create_access_claims_dependency(*, auth_guard: AuthGuard):
    def require_access_claims(
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        return auth_guard.require_access_token(authorization_header=authorization)

    return require_access_claims

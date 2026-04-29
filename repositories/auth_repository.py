from typing import Any

from repositories.helpers.google_oauth_helper import (
    GoogleOAuthHelper,
    GoogleOAuthHelperError,
)


class AuthRepositoryError(Exception):
    def __init__(self, error: str, error_description: str | None = None) -> None:
        self.error = error
        self.error_description = error_description or ""
        super().__init__(self.error_description or self.error)


class AuthRepository:
    def __init__(self, *, google_oauth_helper: GoogleOAuthHelper) -> None:
        self._google_oauth_helper = google_oauth_helper

    def build_google_authorization_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        scopes: list[str],
        state: str,
    ) -> str:
        return self._google_oauth_helper.build_authorization_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            state=state,
        )

    def exchange_google_code(
        self,
        *,
        client_id: str,
        client_secret: str,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, Any]:
        try:
            return self._google_oauth_helper.exchange_code(
                client_id=client_id,
                client_secret=client_secret,
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )
        except GoogleOAuthHelperError as error:
            raise AuthRepositoryError(
                error=error.error,
                error_description=error.error_description,
            ) from error

    def verify_google_id_token(
        self, *, id_token: str, audience: str | None = None
    ) -> dict[str, Any]:
        try:
            return self._google_oauth_helper.verify_id_token(
                id_token=id_token,
                audience=audience,
            )
        except GoogleOAuthHelperError as error:
            raise AuthRepositoryError(
                error=error.error,
                error_description=error.error_description,
            ) from error

from typing import Any

TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleUserSheetsServiceHelperError(Exception):
    pass


class GoogleUserSheetsServiceHelper:
    def build_sheets_service(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        scopes: list[str],
    ) -> Any:
        if not refresh_token:
            raise GoogleUserSheetsServiceHelperError(
                "Google credentials are missing. Reconnect your Google account."
            )
        if not client_id or not client_secret:
            raise GoogleUserSheetsServiceHelperError(
                "Google OAuth client credentials are not configured."
            )
        if not scopes:
            raise GoogleUserSheetsServiceHelperError("Google Sheets scopes are missing.")

        credentials = self._build_credentials(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )
        return self._build_sheets_service(credentials=credentials)

    @staticmethod
    def _build_credentials(
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        scopes: list[str],
    ) -> Any:
        try:
            from google.oauth2.credentials import Credentials
        except ModuleNotFoundError as error:
            raise GoogleUserSheetsServiceHelperError(
                "google-auth is not installed."
            ) from error

        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
        )

    @staticmethod
    def _build_sheets_service(*, credentials: Any) -> Any:
        try:
            from googleapiclient.discovery import build
        except ModuleNotFoundError as error:
            raise GoogleUserSheetsServiceHelperError(
                "google-api-python-client is not installed."
            ) from error

        return build("sheets", "v4", credentials=credentials, cache_discovery=False)

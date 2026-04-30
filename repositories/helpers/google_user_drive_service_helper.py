from typing import Any

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleUserDriveServiceHelperError(Exception):
    pass


class GoogleUserDriveServiceHelper:
    def build_drive_service(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        scopes: list[str] | None = None,
    ) -> Any:
        resolved_scopes = scopes or [DRIVE_FILE_SCOPE]

        if not refresh_token:
            raise GoogleUserDriveServiceHelperError(
                "Google credentials are missing. Reconnect your Google account."
            )
        if not client_id or not client_secret:
            raise GoogleUserDriveServiceHelperError(
                "Google OAuth client credentials are not configured."
            )

        credentials = self._build_credentials(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            scopes=resolved_scopes,
        )
        return self._build_drive_service(credentials=credentials)

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
            raise GoogleUserDriveServiceHelperError(
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
    def _build_drive_service(*, credentials: Any) -> Any:
        try:
            from googleapiclient.discovery import build
        except ModuleNotFoundError as error:
            raise GoogleUserDriveServiceHelperError(
                "google-api-python-client is not installed."
            ) from error

        return build("drive", "v3", credentials=credentials, cache_discovery=False)

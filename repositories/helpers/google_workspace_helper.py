from typing import Any

from repositories.helpers.google_drive_folders_helper import FOLDER_MIME_TYPE

SPREADSHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
TOKEN_URI = "https://oauth2.googleapis.com/token"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
SPREADSHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GoogleWorkspaceHelperError(Exception):
    pass


class GoogleWorkspaceHelper:
    def create_workspace(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        workspace_name: str,
    ) -> dict[str, str | None]:
        credentials = self._build_credentials(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        drive_service = self._build_drive_service(credentials=credentials)

        try:
            folder = (
                drive_service.files()
                .create(
                    body={"name": workspace_name, "mimeType": FOLDER_MIME_TYPE},
                    fields="id,name,webViewLink",
                )
                .execute()
            )
            spreadsheet = (
                drive_service.files()
                .create(
                    body={
                        "name": "Athletes",
                        "mimeType": SPREADSHEET_MIME_TYPE,
                        "parents": [folder["id"]],
                    },
                    fields="id,name,webViewLink",
                )
                .execute()
            )
        except Exception as error:  # pragma: no cover - provider specific failures
            raise GoogleWorkspaceHelperError("Failed to create customer workspace.") from error

        return {
            "workspace_folder_id": folder["id"],
            "workspace_folder_link": folder.get("webViewLink"),
            "doc_id": spreadsheet["id"],
            "doc_link": spreadsheet.get("webViewLink"),
        }

    @staticmethod
    def _build_credentials(
        *, refresh_token: str, client_id: str, client_secret: str
    ) -> Any:
        try:
            from google.oauth2.credentials import Credentials
        except ModuleNotFoundError as error:
            raise GoogleWorkspaceHelperError(
                "google-auth is not installed."
            ) from error

        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=client_id,
            client_secret=client_secret,
            scopes=[DRIVE_FILE_SCOPE, SPREADSHEETS_SCOPE],
        )

    @staticmethod
    def _build_drive_service(*, credentials: Any) -> Any:
        try:
            from googleapiclient.discovery import build
        except ModuleNotFoundError as error:
            raise GoogleWorkspaceHelperError(
                "google-api-python-client is not installed."
            ) from error

        return build("drive", "v3", credentials=credentials, cache_discovery=False)

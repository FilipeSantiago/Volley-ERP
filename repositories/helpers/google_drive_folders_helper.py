import json
import os
from io import BytesIO
from typing import Any

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
SPREADSHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"


class GoogleDriveHelperError(Exception):
    pass


class GoogleDriveFoldersHelper:
    def __init__(self, drive_service: Any | None = None) -> None:
        self._drive_service = drive_service

    def get_drive_service(self) -> Any:
        return self._get_drive_service()

    def find_folder_by_name(
        self, *, folder_name: str, parent_folder_id: str
    ) -> dict[str, str | None] | None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        escaped_name = folder_name.replace("'", "\\'")
        query = (
            f"name = '{escaped_name}' and "
            f"mimeType = '{FOLDER_MIME_TYPE}' and "
            "trashed = false and "
            f"'{parent_folder_id}' in parents"
        )

        try:
            response = (
                self._get_drive_service()
                .files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id,name,webViewLink)",
                    pageSize=1,
                )
                .execute()
            )
        except HttpError as error:
            raise GoogleDriveHelperError(
                "Failed to search folders in Google Drive."
            ) from error

        folders = response.get("files", [])
        if not folders:
            return None

        return self._format_folder(folders[0])

    def list_folders(self, *, parent_folder_id: str) -> list[dict[str, str | None]]:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        query = (
            f"mimeType = '{FOLDER_MIME_TYPE}' and "
            "trashed = false and "
            f"'{parent_folder_id}' in parents"
        )

        items: list[dict[str, str | None]] = []
        next_page_token: str | None = None

        try:
            while True:
                response = (
                    self._get_drive_service()
                    .files()
                    .list(
                        q=query,
                        spaces="drive",
                        fields="nextPageToken,files(id,name,webViewLink)",
                        pageSize=100,
                        orderBy="name_natural",
                        pageToken=next_page_token,
                    )
                    .execute()
                )
                files = response.get("files", [])
                items.extend(self._format_folder(file_item) for file_item in files)

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break
        except HttpError as error:
            raise GoogleDriveHelperError(
                "Failed to list folders in Google Drive."
            ) from error

        return items

    def get_folder_by_id(self, *, folder_id: str) -> dict[str, str | None] | None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        try:
            folder = (
                self._get_drive_service()
                .files()
                .get(fileId=folder_id, fields="id,name,mimeType,webViewLink")
                .execute()
            )
        except HttpError as error:
            if error.resp.status in {403, 404}:
                return None
            raise GoogleDriveHelperError(
                "Failed to fetch folder from Google Drive."
            ) from error

        if folder.get("mimeType") != FOLDER_MIME_TYPE:
            return None

        return self._format_folder(folder)

    def get_file_by_id(self, *, file_id: str) -> dict[str, str | None] | None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        try:
            file_item = (
                self._get_drive_service()
                .files()
                .get(fileId=file_id, fields="id,name,mimeType,webViewLink")
                .execute()
            )
        except HttpError as error:
            if error.resp.status in {403, 404}:
                return None
            raise GoogleDriveHelperError("Failed to fetch file from Google Drive.") from error

        return self._format_file(file_item)

    def download_file(self, *, file_id: str) -> bytes:
        try:
            from googleapiclient.errors import HttpError
            from googleapiclient.http import MediaIoBaseDownload
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        stream = BytesIO()
        request = self._get_drive_service().files().get_media(fileId=file_id)
        downloader = MediaIoBaseDownload(stream, request)
        done = False

        try:
            while not done:
                _, done = downloader.next_chunk()
        except HttpError as error:
            raise GoogleDriveHelperError(
                "Failed to download file from Google Drive."
            ) from error

        return stream.getvalue()

    def find_file_by_name(
        self,
        *,
        file_name: str,
        parent_folder_id: str,
        mime_type: str | None = None,
    ) -> dict[str, str | None] | None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        escaped_name = file_name.replace("'", "\\'")
        query = (
            f"name = '{escaped_name}' and "
            "trashed = false and "
            f"'{parent_folder_id}' in parents"
        )
        if mime_type:
            query = f"{query} and mimeType = '{mime_type}'"

        try:
            response = (
                self._get_drive_service()
                .files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id,name,mimeType,webViewLink)",
                    pageSize=1,
                )
                .execute()
            )
        except HttpError as error:
            raise GoogleDriveHelperError("Failed to search files in Google Drive.") from error

        files = response.get("files", [])
        if not files:
            return None

        return self._format_file(files[0])

    def create_folder(
        self, *, folder_name: str, parent_folder_id: str
    ) -> dict[str, str | None]:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        metadata = {
            "name": folder_name,
            "mimeType": FOLDER_MIME_TYPE,
            "parents": [parent_folder_id],
        }

        try:
            created_folder = (
                self._get_drive_service()
                .files()
                .create(body=metadata, fields="id,name,webViewLink")
                .execute()
            )
        except HttpError as error:
            raise GoogleDriveHelperError(
                "Failed to create folder in Google Drive."
            ) from error

        return self._format_folder(created_folder)

    def create_spreadsheet_file(
        self, *, title: str, parent_folder_id: str
    ) -> dict[str, str | None]:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        metadata = {
            "name": title,
            "mimeType": SPREADSHEET_MIME_TYPE,
            "parents": [parent_folder_id],
        }

        try:
            created_spreadsheet = (
                self._get_drive_service()
                .files()
                .create(body=metadata, fields="id,name,mimeType,webViewLink")
                .execute()
            )
        except HttpError as error:
            raise GoogleDriveHelperError(
                "Failed to create spreadsheet file in Google Drive."
            ) from error

        return self._format_file(created_spreadsheet)

    def upload_file(
        self,
        *,
        file_name: str,
        parent_folder_id: str,
        file_content: bytes,
        mime_type: str | None,
    ) -> dict[str, str | None]:
        try:
            from googleapiclient.errors import HttpError
            from googleapiclient.http import MediaIoBaseUpload
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        metadata = {
            "name": file_name,
            "parents": [parent_folder_id],
        }
        media = MediaIoBaseUpload(
            BytesIO(file_content),
            mimetype=mime_type or "application/octet-stream",
            resumable=False,
        )

        try:
            created_file = (
                self._get_drive_service()
                .files()
                .create(
                    body=metadata,
                    media_body=media,
                    fields="id,name,mimeType,webViewLink",
                )
                .execute()
            )
        except HttpError as error:
            raise GoogleDriveHelperError(
                "Failed to upload file to Google Drive."
            ) from error

        return self._format_file(created_file)

    def _get_drive_service(self) -> Any:
        if self._drive_service is None:
            self._drive_service = self._build_drive_service()
        return self._drive_service

    @staticmethod
    def _build_drive_service() -> Any:
        try:
            from googleapiclient.discovery import build
        except ModuleNotFoundError as error:
            raise GoogleDriveHelperError(
                "google-api-python-client is not installed."
            ) from error

        credentials = _load_google_credentials(scopes=[DRIVE_SCOPE])
        return build("drive", "v3", credentials=credentials, cache_discovery=False)

    @staticmethod
    def _format_folder(raw_folder: dict[str, Any]) -> dict[str, str | None]:
        return {
            "id": raw_folder["id"],
            "name": raw_folder["name"],
            "webViewLink": raw_folder.get("webViewLink"),
        }

    @staticmethod
    def _format_file(raw_file: dict[str, Any]) -> dict[str, str | None]:
        return {
            "id": raw_file["id"],
            "name": raw_file["name"],
            "mimeType": raw_file.get("mimeType"),
            "webViewLink": raw_file.get("webViewLink"),
        }


def _load_google_credentials(scopes: list[str] | None = None):
    resolved_scopes = scopes if scopes is not None else [DRIVE_SCOPE]
    auth_mode = os.getenv("GOOGLE_AUTH_MODE", "adc").strip().lower()

    if auth_mode in {"adc", "auto"}:
        adc_credentials = _load_adc_credentials(scopes=resolved_scopes)
        if adc_credentials is not None:
            return adc_credentials
        if auth_mode == "adc":
            raise GoogleDriveHelperError(
                "Google ADC credentials are not configured. Run "
                "'gcloud auth application-default login' or set GOOGLE_AUTH_MODE="
                "'service_account' with service account credentials."
            )

    if auth_mode not in {"service_account", "auto"}:
        raise GoogleDriveHelperError(
            "Invalid GOOGLE_AUTH_MODE. Use 'adc', 'service_account', or 'auto'."
        )

    try:
        from google.oauth2 import service_account
    except ModuleNotFoundError as error:
        raise GoogleDriveHelperError("google-auth is not installed.") from error

    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if service_account_json:
        try:
            service_account_info = json.loads(service_account_json)
        except json.JSONDecodeError as error:
            raise GoogleDriveHelperError(
                "GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON."
            ) from error
        return service_account.Credentials.from_service_account_info(
            service_account_info, scopes=resolved_scopes
        )

    if credentials_path:
        try:
            return service_account.Credentials.from_service_account_file(
                credentials_path, scopes=resolved_scopes
            )
        except OSError as error:
            raise GoogleDriveHelperError(
                "Could not read GOOGLE_APPLICATION_CREDENTIALS."
            ) from error

    raise GoogleDriveHelperError(
        "Google credentials are not configured. Configure ADC via "
        "'gcloud auth application-default login' (preferred) or set "
        "GOOGLE_AUTH_MODE='service_account' with GOOGLE_SERVICE_ACCOUNT_JSON or "
        "GOOGLE_APPLICATION_CREDENTIALS."
    )


def _load_adc_credentials(*, scopes: list[str]) -> Any | None:
    try:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError
    except ModuleNotFoundError as error:
        raise GoogleDriveHelperError("google-auth is not installed.") from error

    try:
        credentials, _ = google.auth.default(scopes=scopes)
    except DefaultCredentialsError:
        return None
    except Exception as error:
        raise GoogleDriveHelperError("Failed to load ADC credentials.") from error

    return credentials

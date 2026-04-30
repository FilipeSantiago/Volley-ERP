from typing import Any

from repositories.helpers.google_api_error_helper import GoogleAPIErrorHelper
from repositories.helpers.google_user_drive_service_helper import (
    DRIVE_FILE_SCOPE,
    GoogleUserDriveServiceHelper,
    GoogleUserDriveServiceHelperError,
)

FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class GoogleDriveRepositoryError(Exception):
    pass


class GoogleDriveRepository:
    def __init__(
        self, *, user_drive_service_helper: GoogleUserDriveServiceHelper | None = None
    ) -> None:
        self._user_drive_service_helper = (
            user_drive_service_helper or GoogleUserDriveServiceHelper()
        )

    def build_user_drive_service(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> Any:
        try:
            return self._user_drive_service_helper.build_drive_service(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                scopes=[DRIVE_FILE_SCOPE],
            )
        except GoogleUserDriveServiceHelperError as error:
            raise GoogleDriveRepositoryError(
                str(error)
            ) from error

    def get_folder_by_id(
        self, *, drive_service: Any, folder_id: str
    ) -> dict[str, Any] | None:
        try:
            raw = (
                drive_service.files()
                .get(
                    fileId=folder_id,
                    fields="id,name,mimeType,parents,appProperties,webViewLink",
                )
                .execute()
            )
        except Exception as error:  # pragma: no cover - provider specific failure
            if GoogleAPIErrorHelper.http_status(error) == 404:
                return None
            raise GoogleDriveRepositoryError(
                GoogleAPIErrorHelper.map_drive_error(
                    error=error,
                    fallback_message="Failed to fetch Google Drive folder.",
                )
            ) from error

        if raw.get("mimeType") != FOLDER_MIME_TYPE:
            return None
        return self._normalize_folder(raw)

    def find_folder_by_app_properties(
        self,
        *,
        drive_service: Any,
        app_properties: dict[str, str],
        parent_folder_id: str | None = None,
        folder_name: str | None = None,
    ) -> dict[str, Any] | None:
        query_parts = [
            f"mimeType = '{FOLDER_MIME_TYPE}'",
            "trashed = false",
        ]
        if parent_folder_id:
            query_parts.append(f"'{self._escape(parent_folder_id)}' in parents")
        if folder_name:
            query_parts.append(f"name = '{self._escape(folder_name)}'")

        for key, value in app_properties.items():
            escaped_key = self._escape(key)
            escaped_value = self._escape(value)
            query_parts.append(
                "appProperties has "
                f"{{ key='{escaped_key}' and value='{escaped_value}' }}"
            )

        return self._find_single_folder(
            drive_service=drive_service,
            query=" and ".join(query_parts),
        )

    def find_folder_by_name(
        self,
        *,
        drive_service: Any,
        folder_name: str,
        parent_folder_id: str | None = None,
    ) -> dict[str, Any] | None:
        query_parts = [
            f"mimeType = '{FOLDER_MIME_TYPE}'",
            "trashed = false",
            f"name = '{self._escape(folder_name)}'",
        ]
        if parent_folder_id:
            query_parts.append(f"'{self._escape(parent_folder_id)}' in parents")

        return self._find_single_folder(
            drive_service=drive_service,
            query=" and ".join(query_parts),
        )

    def create_folder(
        self,
        *,
        drive_service: Any,
        folder_name: str,
        parent_folder_id: str | None = None,
        app_properties: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": folder_name,
            "mimeType": FOLDER_MIME_TYPE,
        }
        if parent_folder_id:
            body["parents"] = [parent_folder_id]
        if app_properties:
            body["appProperties"] = app_properties

        try:
            raw = (
                drive_service.files()
                .create(
                    body=body,
                    fields="id,name,parents,appProperties,webViewLink",
                )
                .execute()
            )
        except Exception as error:  # pragma: no cover - provider specific failure
            raise GoogleDriveRepositoryError(
                GoogleAPIErrorHelper.map_drive_error(
                    error=error,
                    fallback_message="Failed to create Google Drive folder.",
                )
            ) from error

        return self._normalize_folder(raw)

    def update_folder_app_properties(
        self,
        *,
        drive_service: Any,
        folder_id: str,
        app_properties: dict[str, str],
    ) -> dict[str, Any]:
        try:
            current = self.get_folder_by_id(
                drive_service=drive_service,
                folder_id=folder_id,
            )
            if current is None:
                raise GoogleDriveRepositoryError("Google Drive folder was not found.")
            merged_properties = dict(current.get("appProperties") or {})
            merged_properties.update(app_properties)
            raw = (
                drive_service.files()
                .update(
                    fileId=folder_id,
                    body={"appProperties": merged_properties},
                    fields="id,name,parents,appProperties,webViewLink",
                )
                .execute()
            )
        except GoogleDriveRepositoryError:
            raise
        except Exception as error:  # pragma: no cover - provider specific failure
            raise GoogleDriveRepositoryError(
                GoogleAPIErrorHelper.map_drive_error(
                    error=error,
                    fallback_message="Failed to update Google Drive folder metadata.",
                )
            ) from error

        return self._normalize_folder(raw)

    def ensure_folder(
        self,
        *,
        drive_service: Any,
        folder_name: str,
        app_properties: dict[str, str],
        parent_folder_id: str | None = None,
        fallback_to_name_search: bool = True,
    ) -> dict[str, Any]:
        existing = self.find_folder_by_app_properties(
            drive_service=drive_service,
            app_properties=app_properties,
            parent_folder_id=parent_folder_id,
            folder_name=folder_name,
        )
        if existing is not None:
            return existing

        if fallback_to_name_search:
            by_name = self.find_folder_by_name(
                drive_service=drive_service,
                folder_name=folder_name,
                parent_folder_id=parent_folder_id,
            )
            if by_name is not None:
                return self.update_folder_app_properties(
                    drive_service=drive_service,
                    folder_id=by_name["id"],
                    app_properties=app_properties,
                )

        return self.create_folder(
            drive_service=drive_service,
            folder_name=folder_name,
            parent_folder_id=parent_folder_id,
            app_properties=app_properties,
        )

    def _find_single_folder(self, *, drive_service: Any, query: str) -> dict[str, Any] | None:
        try:
            response = (
                drive_service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="files(id,name,parents,appProperties,webViewLink)",
                    pageSize=1,
                )
                .execute()
            )
        except Exception as error:  # pragma: no cover - provider specific failure
            raise GoogleDriveRepositoryError(
                GoogleAPIErrorHelper.map_drive_error(
                    error=error,
                    fallback_message="Failed to search Google Drive folders.",
                )
            ) from error

        files = response.get("files", [])
        if not files:
            return None
        return self._normalize_folder(files[0])

    @staticmethod
    def _normalize_folder(raw_folder: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": raw_folder["id"],
            "name": raw_folder.get("name"),
            "parents": raw_folder.get("parents") or [],
            "appProperties": raw_folder.get("appProperties") or {},
            "webViewLink": raw_folder.get("webViewLink"),
        }

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

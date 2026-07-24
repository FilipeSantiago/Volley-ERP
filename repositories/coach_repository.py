from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from repositories.helpers.google_drive_folders_helper import (
    GoogleDriveFoldersHelper,
    GoogleDriveHelperError,
)
from repositories.helpers.google_sheets_helper import GoogleSheetsHelper
from repositories.helpers.google_sheets_helper import GoogleSheetsHelperError
from repositories.helpers.google_user_drive_service_helper import (
    DRIVE_FILE_SCOPE,
    GoogleUserDriveServiceHelper,
    GoogleUserDriveServiceHelperError,
)
from repositories.helpers.google_user_sheets_service_helper import (
    GoogleUserSheetsServiceHelper,
    GoogleUserSheetsServiceHelperError,
)

COACH_SHEET_TITLE = "coach"
COACH_HEADERS = [
    "full_name",
    "birthday",
    "cpf",
    "cellphone",
    "tshirt_size",
    "shorts_size",
    "rg",
    "email",
    "photo_link",
    "created_at",
    "updated_at",
    "position",
    "pix_key",
]
PHOTOS_FOLDER_NAME = "photos"
_DRIVE_PATH_ID_PATTERN = re.compile(r"/d/([A-Za-z0-9_-]+)")


class CoachRepositoryError(Exception):
    pass


class CoachRepository:
    def __init__(
        self,
        *,
        user_drive_service_helper: GoogleUserDriveServiceHelper | None = None,
        user_sheets_service_helper: GoogleUserSheetsServiceHelper | None = None,
    ) -> None:
        self._user_drive_service_helper = (
            user_drive_service_helper or GoogleUserDriveServiceHelper()
        )
        self._user_sheets_service_helper = (
            user_sheets_service_helper or GoogleUserSheetsServiceHelper()
        )

    def get_team_coach(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any] | None:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        row = self._get_first_coach_row(
            sheets_helper=sheets_helper,
            spreadsheet_id=spreadsheet_id,
        )
        if row is None:
            return None
        _, values = row
        return self._format_coach_row(values)

    def upsert_team_coach(
        self,
        *,
        spreadsheet_id: str,
        team_id: str,
        images_folder_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        coach: dict[str, Any],
    ) -> dict[str, Any]:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        drive_helper = self._build_drive_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        existing = self._get_first_coach_row(
            sheets_helper=sheets_helper,
            spreadsheet_id=spreadsheet_id,
        )
        existing_values = self._format_coach_row(existing[1]) if existing is not None else None
        photo_link = existing_values.get("photo_link") if isinstance(existing_values, dict) else None

        photo_content = coach.get("photo_content")
        photo_filename = coach.get("photo_filename")
        photo_mime_type = coach.get("photo_mime_type")
        has_photo_payload = any(
            coach.get(field) is not None
            for field in ("photo_content", "photo_filename", "photo_mime_type")
        )

        if has_photo_payload:
            if not isinstance(photo_filename, str) or not photo_filename:
                raise CoachRepositoryError("photo filename is required.")
            if not isinstance(photo_content, bytes) or not photo_content:
                raise CoachRepositoryError("photo content is required.")
            if photo_mime_type is not None and not isinstance(photo_mime_type, str):
                raise CoachRepositoryError("photo mime type is invalid.")
            team_folder = self._get_or_create_folder(
                drive_helper=drive_helper,
                folder_name=f"team_{team_id}",
                parent_folder_id=images_folder_id,
            )
            photos_folder = self._get_or_create_folder(
                drive_helper=drive_helper,
                folder_name=PHOTOS_FOLDER_NAME,
                parent_folder_id=team_folder["id"],
            )
            uploaded = drive_helper.upload_file(
                file_name=photo_filename,
                parent_folder_id=photos_folder["id"],
                file_content=photo_content,
                mime_type=photo_mime_type if isinstance(photo_mime_type, str) else None,
            )
            photo_link = uploaded.get("webViewLink")

        timestamp = _now_iso()
        created_at = (
            existing_values.get("created_at")
            if isinstance(existing_values, dict) and isinstance(existing_values.get("created_at"), str)
            else timestamp
        )

        row = [
            str(coach.get("full_name") or ""),
            str(coach.get("birthday") or ""),
            str(coach.get("cpf") or ""),
            str(coach.get("cellphone") or ""),
            str(coach.get("tshirt_size") or ""),
            str(coach.get("shorts_size") or ""),
            str(coach.get("rg") or ""),
            str(coach.get("email") or ""),
            str(photo_link or ""),
            str(created_at or timestamp),
            timestamp,
            str(coach.get("position") or ""),
            str(coach.get("pix_key") or ""),
        ]

        row_index = existing[0] if existing is not None else 2
        last_column = self._column_label(len(COACH_HEADERS))
        try:
            sheets_helper.update_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{COACH_SHEET_TITLE}!A{row_index}:{last_column}{row_index}",
                values=[row],
            )
        except GoogleSheetsHelperError as error:
            raise CoachRepositoryError("Failed to persist coach data.") from error
        return self._format_coach_row(row)

    def get_team_coach_photo(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any] | None:
        coach = self.get_team_coach(
            spreadsheet_id=spreadsheet_id,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        if coach is None:
            return None
        photo_link = coach.get("photo_link")
        if not isinstance(photo_link, str) or not photo_link.strip():
            return None
        file_id = self._extract_drive_file_id(photo_link)
        if not file_id:
            raise CoachRepositoryError("Invalid coach photo link.")

        drive_helper = self._build_drive_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            file_item = drive_helper.get_file_by_id(file_id=file_id)
            if file_item is None:
                return None
            content = drive_helper.download_file(file_id=file_id)
        except GoogleDriveHelperError as error:
            raise CoachRepositoryError("Failed to fetch coach photo.") from error

        return {
            "content": content,
            "mime_type": file_item.get("mimeType"),
            "file_name": file_item.get("name"),
            "photo_link": photo_link,
            "full_name": coach.get("full_name"),
        }

    def _get_first_coach_row(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
    ) -> tuple[int, list[str]] | None:
        try:
            self._ensure_coach_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            self._ensure_coach_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            last_column = self._column_label(len(COACH_HEADERS))
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{COACH_SHEET_TITLE}!A2:{last_column}",
            )
        except GoogleSheetsHelperError as error:
            raise CoachRepositoryError("Failed to fetch coach data.") from error

        for row_index, row in enumerate(rows, start=2):
            if any(str(value).strip() for value in row):
                return row_index, row
        return None

    def _ensure_coach_sheet_exists(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
    ) -> None:
        spreadsheet = sheets_helper.get_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            fields="sheets(properties(title))",
        )
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties")
            if isinstance(properties, dict) and properties.get("title") == COACH_SHEET_TITLE:
                return
        sheets_helper.add_sheet(
            spreadsheet_id=spreadsheet_id,
            sheet_title=COACH_SHEET_TITLE,
        )

    def _ensure_coach_header(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
    ) -> None:
        current_header = sheets_helper.get_values(
            spreadsheet_id=spreadsheet_id,
            range_name=f"{COACH_SHEET_TITLE}!1:1",
        )
        if current_header:
            header_row = current_header[0]
            if len(header_row) >= len(COACH_HEADERS):
                return
            for index in range(len(header_row), len(COACH_HEADERS)):
                column = self._column_label(index + 1)
                sheets_helper.update_values(
                    spreadsheet_id=spreadsheet_id,
                    range_name=f"{COACH_SHEET_TITLE}!{column}1:{column}1",
                    values=[[COACH_HEADERS[index]]],
                )
            return

        last_column = self._column_label(len(COACH_HEADERS))
        sheets_helper.update_values(
            spreadsheet_id=spreadsheet_id,
            range_name=f"{COACH_SHEET_TITLE}!A1:{last_column}1",
            values=[COACH_HEADERS],
        )

    def _build_drive_helper(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> GoogleDriveFoldersHelper:
        try:
            drive_service = self._user_drive_service_helper.build_drive_service(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                scopes=[DRIVE_FILE_SCOPE],
            )
        except GoogleUserDriveServiceHelperError as error:
            raise CoachRepositoryError(str(error)) from error
        return GoogleDriveFoldersHelper(drive_service=drive_service)

    def _build_sheets_helper(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> GoogleSheetsHelper:
        try:
            sheets_service = self._user_sheets_service_helper.build_sheets_service(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
        except GoogleUserSheetsServiceHelperError as error:
            raise CoachRepositoryError(str(error)) from error
        return GoogleSheetsHelper(sheets_service=sheets_service)

    @staticmethod
    def _get_or_create_folder(
        *,
        drive_helper: GoogleDriveFoldersHelper,
        folder_name: str,
        parent_folder_id: str,
    ) -> dict[str, str | None]:
        folder = drive_helper.find_folder_by_name(
            folder_name=folder_name,
            parent_folder_id=parent_folder_id,
        )
        if folder is not None:
            return folder
        return drive_helper.create_folder(
            folder_name=folder_name,
            parent_folder_id=parent_folder_id,
        )

    @staticmethod
    def _format_coach_row(row: list[Any]) -> dict[str, Any]:
        serialized = [str(value).strip() for value in row[: len(COACH_HEADERS)]]
        if len(serialized) < len(COACH_HEADERS):
            serialized.extend([""] * (len(COACH_HEADERS) - len(serialized)))
        record: dict[str, Any] = dict(zip(COACH_HEADERS, serialized))
        optional_fields = (
            "tshirt_size",
            "shorts_size",
            "position",
            "rg",
            "email",
            "photo_link",
            "created_at",
            "updated_at",
        )
        for field in optional_fields:
            if not record.get(field):
                record[field] = None
        return record

    @staticmethod
    def _column_label(index: int) -> str:
        label = ""
        value = index
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            label = chr(ord("A") + remainder) + label
        return label

    @staticmethod
    def _extract_drive_file_id(photo_link: str) -> str | None:
        normalized = photo_link.strip()
        if not normalized:
            return None
        if all(token not in normalized for token in ("://", "/", "?", "#")):
            return normalized

        parsed = urlparse(normalized)
        query = parse_qs(parsed.query)
        file_ids = query.get("id")
        if file_ids:
            candidate = file_ids[0].strip()
            if candidate:
                return candidate

        match = _DRIVE_PATH_ID_PATTERN.search(parsed.path)
        if match:
            return match.group(1).strip()
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import parse_qs, urlparse
import uuid

from repositories.helpers.google_drive_folders_helper import (
    GoogleDriveFoldersHelper,
    GoogleDriveHelperError,
    SPREADSHEET_MIME_TYPE,
)
from repositories.helpers.google_sheets_helper import GoogleSheetsHelper, GoogleSheetsHelperError
from repositories.helpers.google_user_drive_service_helper import (
    DRIVE_FILE_SCOPE,
    GoogleUserDriveServiceHelper,
    GoogleUserDriveServiceHelperError,
)
from repositories.helpers.google_user_sheets_service_helper import (
    GoogleUserSheetsServiceHelper,
    GoogleUserSheetsServiceHelperError,
)

ATHLETES_SHEET_TITLE = "Athletes"
ATHLETES_HEADERS = [
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
    "athlete_id",
    "position",
]
PHOTOS_FOLDER_NAME = "photos"
_DRIVE_PATH_ID_PATTERN = re.compile(r"/d/([A-Za-z0-9_-]+)")


class TeamWorkspaceRepositoryError(Exception):
    pass


class TeamWorkspaceRepository:
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

    def create_team_spreadsheet(
        self,
        *,
        team_id: str,
        team_name: str | None,
        sheets_folder_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, str | None]:
        drive_helper = self._build_drive_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )

        if isinstance(team_name, str) and team_name.strip():
            title = f"{team_name.strip()} ({team_id})"
        else:
            title = f"team_{team_id}"

        try:
            spreadsheet = drive_helper.find_file_by_name(
                file_name=title,
                parent_folder_id=sheets_folder_id,
                mime_type=SPREADSHEET_MIME_TYPE,
            )
            if spreadsheet is None:
                spreadsheet = drive_helper.create_spreadsheet_file(
                    title=title,
                    parent_folder_id=sheets_folder_id,
                )
            spreadsheet_id = spreadsheet["id"]
            self._ensure_athletes_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
        except (GoogleDriveHelperError, GoogleSheetsHelperError) as error:
            raise TeamWorkspaceRepositoryError(
                "Failed to provision team spreadsheet."
            ) from error

        return {
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": spreadsheet.get("webViewLink"),
        }

    def append_team_athlete(
        self,
        *,
        org_id: str,
        team_id: str,
        spreadsheet_id: str,
        images_folder_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        athlete: dict[str, str | bytes | None],
    ) -> dict[str, str | None]:
        drive_helper = self._build_drive_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )

        file_name = athlete.get("photo_filename")
        file_content = athlete.get("photo_content")
        mime_type = athlete.get("photo_mime_type")
        if not isinstance(file_name, str) or not file_name:
            raise TeamWorkspaceRepositoryError("photo filename is required.")
        if not isinstance(file_content, bytes) or not file_content:
            raise TeamWorkspaceRepositoryError("photo content is required.")
        if mime_type is not None and not isinstance(mime_type, str):
            raise TeamWorkspaceRepositoryError("photo mime type is invalid.")

        try:
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
                file_name=file_name,
                parent_folder_id=photos_folder["id"],
                file_content=file_content,
                mime_type=mime_type,
            )

            self._ensure_athletes_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            self._ensure_athletes_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )

            timestamp = _now_iso()
            athlete_id = str(uuid.uuid4())
            photo_link = uploaded.get("webViewLink") or ""
            row = [
                str(athlete.get("full_name") or ""),
                str(athlete.get("birthday") or ""),
                str(athlete.get("cpf") or ""),
                str(athlete.get("cellphone") or ""),
                str(athlete.get("tshirt_size") or ""),
                str(athlete.get("shorts_size") or ""),
                str(athlete.get("rg") or ""),
                str(athlete.get("email") or ""),
                photo_link,
                timestamp,
                timestamp,
                athlete_id,
                str(athlete.get("position") or ""),
            ]
            sheets_helper.append_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!A1",
                values=[row],
                value_input_option="RAW",
            )
        except (GoogleDriveHelperError, GoogleSheetsHelperError) as error:
            raise TeamWorkspaceRepositoryError(
                "Failed to persist athlete data."
            ) from error

        return {
            "org_id": org_id,
            "team_id": team_id,
            "photo_link": photo_link or None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "athlete_id": athlete_id,
        }

    def update_team_athlete(
        self,
        *,
        org_id: str,
        team_id: str,
        spreadsheet_id: str,
        images_folder_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        athlete: dict[str, str | bytes | None],
    ) -> dict[str, str | None] | None:
        normalized_athlete_id = athlete.get("athlete_id")
        if not isinstance(normalized_athlete_id, str) or not normalized_athlete_id.strip():
            raise TeamWorkspaceRepositoryError("athlete_id is required.")

        file_name = athlete.get("photo_filename")
        file_content = athlete.get("photo_content")
        mime_type = athlete.get("photo_mime_type")
        has_photo_payload = any(
            athlete.get(field) is not None
            for field in ("photo_content", "photo_filename", "photo_mime_type")
        )
        if has_photo_payload:
            if not isinstance(file_name, str) or not file_name:
                raise TeamWorkspaceRepositoryError("photo filename is required.")
            if not isinstance(file_content, bytes) or not file_content:
                raise TeamWorkspaceRepositoryError("photo content is required.")
            if mime_type is not None and not isinstance(mime_type, str):
                raise TeamWorkspaceRepositoryError("photo mime type is invalid.")
            if not isinstance(images_folder_id, str) or not images_folder_id.strip():
                raise TeamWorkspaceRepositoryError("images folder is required.")

        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        drive_helper = (
            self._build_drive_helper(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
            )
            if has_photo_payload
            else None
        )

        try:
            self._ensure_athletes_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            self._ensure_athletes_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!A2:M",
            )
            self._backfill_athlete_ids(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                rows=rows,
            )

            for row_index, row in enumerate(rows, start=2):
                formatted = self._format_athlete_row(row)
                if formatted["athlete_id"] != normalized_athlete_id.strip():
                    continue

                photo_link = formatted.get("photo_link") or ""
                if has_photo_payload:
                    if drive_helper is None:
                        raise TeamWorkspaceRepositoryError("Failed to update athlete data.")
                    if not isinstance(file_name, str) or not isinstance(file_content, bytes):
                        raise TeamWorkspaceRepositoryError("photo payload is invalid.")
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
                        file_name=file_name,
                        parent_folder_id=photos_folder["id"],
                        file_content=file_content,
                        mime_type=mime_type if isinstance(mime_type, str) else None,
                    )
                    photo_link = uploaded.get("webViewLink") or ""

                timestamp = _now_iso()
                created_at = formatted.get("created_at") or timestamp
                updated_row = [
                    str(athlete.get("full_name") or ""),
                    str(athlete.get("birthday") or ""),
                    str(athlete.get("cpf") or ""),
                    str(athlete.get("cellphone") or ""),
                    str(athlete.get("tshirt_size") or ""),
                    str(athlete.get("shorts_size") or ""),
                    str(athlete.get("rg") or ""),
                    str(athlete.get("email") or ""),
                    photo_link,
                    created_at,
                    timestamp,
                    normalized_athlete_id.strip(),
                    str(athlete.get("position") or ""),
                ]
                sheets_helper.update_values(
                    spreadsheet_id=spreadsheet_id,
                    range_name=f"{ATHLETES_SHEET_TITLE}!A{row_index}:M{row_index}",
                    values=[updated_row],
                )
                return {
                    "org_id": org_id,
                    "team_id": team_id,
                    "athlete_id": normalized_athlete_id.strip(),
                    "photo_link": photo_link or None,
                    "created_at": created_at,
                    "updated_at": timestamp,
                }
        except (GoogleDriveHelperError, GoogleSheetsHelperError) as error:
            raise TeamWorkspaceRepositoryError(
                "Failed to update athlete data."
            ) from error

        return None

    def list_team_athletes(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any]:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            spreadsheet = sheets_helper.get_spreadsheet(
                spreadsheet_id=spreadsheet_id,
                fields="sheets(properties(title))",
            )
            sheet_titles = []
            for sheet in spreadsheet.get("sheets", []):
                properties = sheet.get("properties")
                if isinstance(properties, dict):
                    title = properties.get("title")
                    if isinstance(title, str):
                        sheet_titles.append(title)
            if ATHLETES_SHEET_TITLE not in sheet_titles:
                return {"items": []}
            self._ensure_athletes_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!A2:M",
            )
        except GoogleSheetsHelperError as error:
            raise TeamWorkspaceRepositoryError("Failed to fetch team athletes.") from error

        self._backfill_athlete_ids(
            sheets_helper=sheets_helper,
            spreadsheet_id=spreadsheet_id,
            rows=rows,
        )
        return {"items": [self._format_athlete_row(row) for row in rows]}

    def find_team_athlete_by_id(
        self,
        *,
        spreadsheet_id: str,
        athlete_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any] | None:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            self._ensure_athletes_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            self._ensure_athletes_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
            )
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!A2:M",
            )
            self._backfill_athlete_ids(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                rows=rows,
            )
        except GoogleSheetsHelperError as error:
            raise TeamWorkspaceRepositoryError("Failed to resolve athlete photo.") from error

        normalized_athlete_id = athlete_id.strip()
        for row in rows:
            formatted = self._format_athlete_row(row)
            if formatted["athlete_id"] != normalized_athlete_id:
                continue
            return {
                "athlete_id": formatted["athlete_id"],
                "photo_link": formatted["photo_link"],
                "full_name": formatted["full_name"],
            }
        return None

    def get_team_athlete_photo_by_id(
        self,
        *,
        spreadsheet_id: str,
        athlete_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> dict[str, Any] | None:
        athlete = self.find_team_athlete_by_id(
            spreadsheet_id=spreadsheet_id,
            athlete_id=athlete_id,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        if athlete is None:
            return None

        photo_link = athlete.get("photo_link")
        if not isinstance(photo_link, str) or not photo_link.strip():
            return None
        file_id = self._extract_drive_file_id(photo_link)
        if not file_id:
            raise TeamWorkspaceRepositoryError("Invalid athlete photo link.")

        drive_helper = self._build_drive_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            photo_file = drive_helper.get_file_by_id(file_id=file_id)
            if photo_file is None:
                return None
            content = drive_helper.download_file(file_id=file_id)
        except GoogleDriveHelperError as error:
            raise TeamWorkspaceRepositoryError("Failed to fetch athlete photo.") from error

        return {
            "athlete_id": athlete["athlete_id"],
            "full_name": athlete.get("full_name"),
            "file_name": photo_file.get("name"),
            "mime_type": photo_file.get("mimeType"),
            "content": content,
        }

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
            raise TeamWorkspaceRepositoryError(str(error)) from error
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
            raise TeamWorkspaceRepositoryError(str(error)) from error
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

    def _ensure_athletes_sheet_exists(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
    ) -> None:
        spreadsheet = sheets_helper.get_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            fields="sheets(properties(sheetId,title))",
        )
        sheets = spreadsheet.get("sheets") or []
        for sheet in sheets:
            properties = sheet.get("properties")
            if isinstance(properties, dict) and properties.get("title") == ATHLETES_SHEET_TITLE:
                return

        first = sheets[0].get("properties") if sheets else None
        if isinstance(first, dict) and isinstance(first.get("sheetId"), int):
            sheets_helper.rename_sheet(
                spreadsheet_id=spreadsheet_id,
                sheet_id=first["sheetId"],
                new_title=ATHLETES_SHEET_TITLE,
            )
            return

        sheets_helper.add_sheet(
            spreadsheet_id=spreadsheet_id,
            sheet_title=ATHLETES_SHEET_TITLE,
        )

    def _ensure_athletes_header(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
    ) -> None:
        current_header = sheets_helper.get_values(
            spreadsheet_id=spreadsheet_id,
            range_name=f"{ATHLETES_SHEET_TITLE}!1:1",
        )
        if current_header:
            header_row = current_header[0]
            if len(header_row) >= len(ATHLETES_HEADERS):
                return
            # Keep existing columns untouched and only append missing header names.
            for index in range(len(header_row), len(ATHLETES_HEADERS)):
                column = self._column_label(index + 1)
                sheets_helper.update_values(
                    spreadsheet_id=spreadsheet_id,
                    range_name=f"{ATHLETES_SHEET_TITLE}!{column}1:{column}1",
                    values=[[ATHLETES_HEADERS[index]]],
                )
            return
        sheets_helper.update_values(
            spreadsheet_id=spreadsheet_id,
            range_name=f"{ATHLETES_SHEET_TITLE}!A1:M1",
            values=[ATHLETES_HEADERS],
        )

    @staticmethod
    def _format_athlete_row(row: list[Any]) -> dict[str, Any]:
        serialized = [str(value).strip() for value in row[: len(ATHLETES_HEADERS)]]
        if len(serialized) < len(ATHLETES_HEADERS):
            serialized.extend([""] * (len(ATHLETES_HEADERS) - len(serialized)))
        record: dict[str, Any] = dict(zip(ATHLETES_HEADERS, serialized))
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

    def _backfill_athlete_ids(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
        rows: list[list[str]],
    ) -> None:
        athlete_id_index = ATHLETES_HEADERS.index("athlete_id")
        athlete_id_column = self._column_label(athlete_id_index + 1)
        for row_index, row in enumerate(rows, start=2):
            existing_id = row[athlete_id_index].strip() if len(row) > athlete_id_index else ""
            if existing_id:
                continue
            generated_id = str(uuid.uuid4())
            if len(row) <= athlete_id_index:
                row.extend([""] * ((athlete_id_index + 1) - len(row)))
            row[athlete_id_index] = generated_id
            sheets_helper.update_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!{athlete_id_column}{row_index}:{athlete_id_column}{row_index}",
                values=[[generated_id]],
            )

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

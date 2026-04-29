from typing import Any

from repositories.helpers.google_drive_folders_helper import (
    GoogleDriveFoldersHelper,
    GoogleDriveHelperError,
    SPREADSHEET_MIME_TYPE,
)
from repositories.helpers.google_sheets_helper import (
    GoogleSheetsHelper,
    GoogleSheetsHelperError,
)

PHOTOS_FOLDER_NAME = "photos"
ATHLETES_SPREADSHEET_NAME = "Athletes"
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
]


class AthleteRepositoryError(Exception):
    pass


class TeamFolderAccessError(AthleteRepositoryError):
    pass


class AthleteRepository:
    def __init__(
        self,
        *,
        drive_folders_helper: GoogleDriveFoldersHelper,
        sheets_helper: GoogleSheetsHelper,
    ) -> None:
        self._drive_folders_helper = drive_folders_helper
        self._sheets_helper = sheets_helper

    def ensure_team_folder_exists(self, *, team_folder_id: str) -> dict[str, str | None]:
        try:
            team_folder = self._drive_folders_helper.get_folder_by_id(
                folder_id=team_folder_id
            )
        except GoogleDriveHelperError as error:
            raise AthleteRepositoryError(
                "Failed to resolve team folder in Google Drive."
            ) from error

        if team_folder is None:
            raise TeamFolderAccessError(
                "Provided team_folder_id is invalid or inaccessible."
            )

        return team_folder

    def get_or_create_photos_folder(
        self, *, team_folder_id: str
    ) -> dict[str, str | None]:
        try:
            photos_folder = self._drive_folders_helper.find_folder_by_name(
                folder_name=PHOTOS_FOLDER_NAME,
                parent_folder_id=team_folder_id,
            )
            if photos_folder is not None:
                return photos_folder

            return self._drive_folders_helper.create_folder(
                folder_name=PHOTOS_FOLDER_NAME,
                parent_folder_id=team_folder_id,
            )
        except GoogleDriveHelperError as error:
            raise AthleteRepositoryError(
                "Failed to resolve photos folder in Google Drive."
            ) from error

    def upload_photo(
        self,
        *,
        photos_folder_id: str,
        file_name: str,
        file_content: bytes,
        mime_type: str | None,
    ) -> dict[str, str | None]:
        try:
            return self._drive_folders_helper.upload_file(
                file_name=file_name,
                parent_folder_id=photos_folder_id,
                file_content=file_content,
                mime_type=mime_type,
            )
        except GoogleDriveHelperError as error:
            raise AthleteRepositoryError("Failed to upload athlete photo.") from error

    def append_to_team_athletes_sheet(
        self, *, team_folder_id: str, athlete_row: list[str]
    ) -> dict[str, str]:
        spreadsheet = self._get_or_create_athletes_spreadsheet(
            team_folder_id=team_folder_id
        )
        spreadsheet_id = spreadsheet["id"]

        self._ensure_athletes_sheet_exists(spreadsheet_id=spreadsheet_id)
        self._ensure_athletes_header(spreadsheet_id=spreadsheet_id)

        try:
            self._sheets_helper.append_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!A1",
                values=[athlete_row],
            )
        except GoogleSheetsHelperError as error:
            raise AthleteRepositoryError("Failed to append athlete row.") from error

        return {"spreadsheet_id": spreadsheet_id, "sheet_title": ATHLETES_SHEET_TITLE}

    def list_team_athletes(self, *, team_folder_id: str) -> dict[str, Any]:
        try:
            spreadsheet = self._drive_folders_helper.find_file_by_name(
                file_name=ATHLETES_SPREADSHEET_NAME,
                parent_folder_id=team_folder_id,
                mime_type=SPREADSHEET_MIME_TYPE,
            )
        except GoogleDriveHelperError as error:
            raise AthleteRepositoryError("Failed to resolve Athletes spreadsheet.") from error

        if spreadsheet is None:
            return {"spreadsheet_id": None, "items": []}

        spreadsheet_id = spreadsheet["id"]
        try:
            spreadsheet_metadata = self._sheets_helper.get_spreadsheet(
                spreadsheet_id=spreadsheet_id,
                fields="sheets.properties.title",
            )
            sheet_titles = [
                sheet["properties"]["title"]
                for sheet in spreadsheet_metadata.get("sheets", [])
            ]
            if ATHLETES_SHEET_TITLE not in sheet_titles:
                return {"spreadsheet_id": spreadsheet_id, "items": []}

            athlete_rows = self._sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!A2:K",
            )
        except GoogleSheetsHelperError as error:
            raise AthleteRepositoryError("Failed to fetch athlete rows.") from error

        items = [self._format_athlete_row(row) for row in athlete_rows]
        return {"spreadsheet_id": spreadsheet_id, "items": items}

    def _get_or_create_athletes_spreadsheet(
        self, *, team_folder_id: str
    ) -> dict[str, str | None]:
        try:
            spreadsheet = self._drive_folders_helper.find_file_by_name(
                file_name=ATHLETES_SPREADSHEET_NAME,
                parent_folder_id=team_folder_id,
                mime_type=SPREADSHEET_MIME_TYPE,
            )
            if spreadsheet is not None:
                return spreadsheet

            return self._drive_folders_helper.create_spreadsheet_file(
                title=ATHLETES_SPREADSHEET_NAME,
                parent_folder_id=team_folder_id,
            )
        except GoogleDriveHelperError as error:
            raise AthleteRepositoryError("Failed to resolve Athletes spreadsheet.") from error

    def _ensure_athletes_sheet_exists(self, *, spreadsheet_id: str) -> None:
        try:
            spreadsheet = self._sheets_helper.get_spreadsheet(
                spreadsheet_id=spreadsheet_id,
                fields="sheets.properties.title",
            )
            sheet_titles = [
                sheet["properties"]["title"] for sheet in spreadsheet.get("sheets", [])
            ]
            if ATHLETES_SHEET_TITLE in sheet_titles:
                return

            self._sheets_helper.add_sheet(
                spreadsheet_id=spreadsheet_id,
                sheet_title=ATHLETES_SHEET_TITLE,
            )
        except GoogleSheetsHelperError as error:
            raise AthleteRepositoryError(
                "Failed to ensure Athletes sheet exists."
            ) from error

    def _ensure_athletes_header(self, *, spreadsheet_id: str) -> None:
        try:
            current_header = self._sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!1:1",
            )
            if current_header:
                return

            self._sheets_helper.update_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{ATHLETES_SHEET_TITLE}!A1:K1",
                values=[ATHLETES_HEADERS],
            )
        except GoogleSheetsHelperError as error:
            raise AthleteRepositoryError(
                "Failed to ensure Athletes sheet header."
            ) from error

    @staticmethod
    def _format_athlete_row(row: list[Any]) -> dict[str, str]:
        serialized = [str(value).strip() for value in row[: len(ATHLETES_HEADERS)]]
        if len(serialized) < len(ATHLETES_HEADERS):
            serialized.extend([""] * (len(ATHLETES_HEADERS) - len(serialized)))
        return dict(zip(ATHLETES_HEADERS, serialized))

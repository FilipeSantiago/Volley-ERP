from typing import Any

from repositories.helpers.google_drive_folders_helper import (
    DRIVE_SCOPE,
    _load_google_credentials,
)

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GoogleSheetsHelperError(Exception):
    pass


class GoogleSheetsHelper:
    def __init__(self, sheets_service: Any | None = None) -> None:
        self._sheets_service = sheets_service

    def get_spreadsheet(self, *, spreadsheet_id: str, fields: str) -> dict[str, Any]:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleSheetsHelperError(
                "google-api-python-client is not installed."
            ) from error

        try:
            return (
                self._get_sheets_service()
                .spreadsheets()
                .get(spreadsheetId=spreadsheet_id, fields=fields)
                .execute()
            )
        except HttpError as error:
            raise GoogleSheetsHelperError("Failed to fetch spreadsheet.") from error

    def add_sheet(self, *, spreadsheet_id: str, sheet_title: str) -> None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleSheetsHelperError(
                "google-api-python-client is not installed."
            ) from error

        body = {"requests": [{"addSheet": {"properties": {"title": sheet_title}}}]}

        try:
            (
                self._get_sheets_service()
                .spreadsheets()
                .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
                .execute()
            )
        except HttpError as error:
            raise GoogleSheetsHelperError("Failed to add spreadsheet sheet.") from error

    def rename_sheet(self, *, spreadsheet_id: str, sheet_id: int, new_title: str) -> None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleSheetsHelperError(
                "google-api-python-client is not installed."
            ) from error

        body = {
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": sheet_id, "title": new_title},
                        "fields": "title",
                    }
                }
            ]
        }

        try:
            (
                self._get_sheets_service()
                .spreadsheets()
                .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
                .execute()
            )
        except HttpError as error:
            raise GoogleSheetsHelperError("Failed to rename spreadsheet sheet.") from error

    def get_values(self, *, spreadsheet_id: str, range_name: str) -> list[list[str]]:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleSheetsHelperError(
                "google-api-python-client is not installed."
            ) from error

        try:
            response = (
                self._get_sheets_service()
                .spreadsheets()
                .values()
                .get(spreadsheetId=spreadsheet_id, range=range_name)
                .execute()
            )
        except HttpError as error:
            raise GoogleSheetsHelperError("Failed to fetch spreadsheet values.") from error

        return response.get("values", [])

    def update_values(
        self, *, spreadsheet_id: str, range_name: str, values: list[list[str]]
    ) -> None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleSheetsHelperError(
                "google-api-python-client is not installed."
            ) from error

        body = {"values": values}

        try:
            (
                self._get_sheets_service()
                .spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    body=body,
                )
                .execute()
            )
        except HttpError as error:
            raise GoogleSheetsHelperError("Failed to update spreadsheet values.") from error

    def append_values(
        self,
        *,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[str]],
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        try:
            from googleapiclient.errors import HttpError
        except ModuleNotFoundError as error:
            raise GoogleSheetsHelperError(
                "google-api-python-client is not installed."
            ) from error

        body = {"values": values}
        normalized_value_input_option = value_input_option.strip().upper()
        if normalized_value_input_option not in {"USER_ENTERED", "RAW"}:
            raise GoogleSheetsHelperError("Invalid value_input_option.")

        try:
            (
                self._get_sheets_service()
                .spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption=normalized_value_input_option,
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )
        except HttpError as error:
            raise GoogleSheetsHelperError("Failed to append spreadsheet values.") from error

    def _get_sheets_service(self) -> Any:
        if self._sheets_service is None:
            self._sheets_service = self._build_sheets_service()
        return self._sheets_service

    @staticmethod
    def _build_sheets_service() -> Any:
        try:
            from googleapiclient.discovery import build
        except ModuleNotFoundError as error:
            raise GoogleSheetsHelperError(
                "google-api-python-client is not installed."
            ) from error

        credentials = _load_google_credentials(scopes=[DRIVE_SCOPE, SHEETS_SCOPE])
        return build("sheets", "v4", credentials=credentials, cache_discovery=False)

from __future__ import annotations

from typing import Any

from repositories.helpers.google_sheets_helper import GoogleSheetsHelper
from repositories.helpers.google_sheets_helper import GoogleSheetsHelperError
from repositories.helpers.google_user_sheets_service_helper import (
    GoogleUserSheetsServiceHelper,
    GoogleUserSheetsServiceHelperError,
)

MONTHLY_FEES_SHEET_TITLE = "monthly_fees"
MONTHLY_FEES_HEADERS = [
    "entry_id",
    "org_id",
    "team_id",
    "year",
    "month",
    "entry_date",
    "tag",
    "direction",
    "amount",
    "currency",
    "athlete_id",
    "person_id",
    "person_name",
    "description",
    "source",
    "created_at",
    "updated_at",
    "is_active",
]
MONTHLY_FINANCIAL_CONFIG_SHEET_TITLE = "monthly_financial_config"
MONTHLY_FINANCIAL_CONFIG_HEADERS = [
    "team_id",
    "monthly_contribution_amount",
    "court_monthly_amount",
    "training_weekdays",
    "currency",
    "is_active",
    "created_at",
    "updated_at",
]
MONTHLY_FINANCIAL_PEOPLE_CONFIG_SHEET_TITLE = "monthly_financial_people_config"
MONTHLY_FINANCIAL_PEOPLE_CONFIG_HEADERS = [
    "config_id",
    "team_id",
    "person_id",
    "person_name",
    "role",
    "amount_type",
    "amount",
    "is_active",
    "created_at",
    "updated_at",
]


class MonthlyFeesRepositoryError(Exception):
    pass


class MonthlyFeesRepository:
    def __init__(
        self,
        *,
        user_sheets_service_helper: GoogleUserSheetsServiceHelper | None = None,
    ) -> None:
        self._user_sheets_service_helper = (
            user_sheets_service_helper or GoogleUserSheetsServiceHelper()
        )

    def list_monthly_fee_entries(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> list[dict[str, Any]]:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            self._ensure_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
            )
            self._ensure_sheet_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
                headers=MONTHLY_FEES_HEADERS,
            )
            sheet_headers = self._get_sheet_headers(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
                default_headers=MONTHLY_FEES_HEADERS,
            )
            last_column = self._column_label(len(sheet_headers))
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{MONTHLY_FEES_SHEET_TITLE}!A2:{last_column}",
            )
        except GoogleSheetsHelperError as error:
            raise MonthlyFeesRepositoryError("Failed to fetch monthly fees entries.") from error

        items: list[dict[str, Any]] = []
        for row in rows:
            item = self._row_to_record(row=row, headers=sheet_headers)
            if not item.get("entry_id"):
                continue
            items.append(item)
        return items

    def append_monthly_fee_entries(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not entries:
            return []
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            self._ensure_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
            )
            self._ensure_sheet_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
                headers=MONTHLY_FEES_HEADERS,
            )
            sheet_headers = self._get_sheet_headers(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
                default_headers=MONTHLY_FEES_HEADERS,
            )
            rows = [
                self._record_to_row(record=entry, headers=sheet_headers)
                for entry in entries
            ]
            sheets_helper.append_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{MONTHLY_FEES_SHEET_TITLE}!A1",
                values=rows,
                value_input_option="USER_ENTERED",
            )
        except GoogleSheetsHelperError as error:
            raise MonthlyFeesRepositoryError("Failed to persist monthly fees entries.") from error
        return entries

    def update_monthly_fee_entry(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        entry_id: str,
        expected_team_id: str | None,
        expected_source: str | None,
        amount: float | None,
        currency: str | None,
        description: str | None,
        is_active: bool | None,
        updated_at: str,
    ) -> dict[str, Any] | None:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            self._ensure_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
            )
            self._ensure_sheet_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
                headers=MONTHLY_FEES_HEADERS,
            )
            sheet_headers = self._get_sheet_headers(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FEES_SHEET_TITLE,
                default_headers=MONTHLY_FEES_HEADERS,
            )
            last_column = self._column_label(len(sheet_headers))
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{MONTHLY_FEES_SHEET_TITLE}!A2:{last_column}",
            )
        except GoogleSheetsHelperError as error:
            raise MonthlyFeesRepositoryError("Failed to fetch monthly fees entries.") from error

        for row_index, row in enumerate(rows, start=2):
            item = self._row_to_record(row=row, headers=sheet_headers)
            current_entry_id = item.get("entry_id")
            if not isinstance(current_entry_id, str) or current_entry_id != entry_id:
                continue
            if expected_team_id is not None and item.get("team_id") != expected_team_id:
                continue
            if expected_source is not None:
                current_source = str(item.get("source") or "").strip().upper()
                if current_source != expected_source:
                    continue

            if amount is not None:
                item["amount"] = str(amount)
            if currency is not None:
                item["currency"] = currency
            if description is not None:
                item["description"] = description
            if is_active is not None:
                item["is_active"] = "true" if is_active else "false"
            item["updated_at"] = updated_at
            updated_row = self._record_to_row(record=item, headers=sheet_headers)
            try:
                sheets_helper.update_values(
                    spreadsheet_id=spreadsheet_id,
                    range_name=f"{MONTHLY_FEES_SHEET_TITLE}!A{row_index}:{last_column}{row_index}",
                    values=[updated_row],
                )
            except GoogleSheetsHelperError as error:
                raise MonthlyFeesRepositoryError("Failed to update monthly fee entry.") from error
            return self._row_to_record(row=updated_row, headers=sheet_headers)

        return None

    def get_monthly_financial_config(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        team_id: str,
    ) -> dict[str, Any] | None:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            self._ensure_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FINANCIAL_CONFIG_SHEET_TITLE,
            )
            self._ensure_sheet_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FINANCIAL_CONFIG_SHEET_TITLE,
                headers=MONTHLY_FINANCIAL_CONFIG_HEADERS,
            )
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{MONTHLY_FINANCIAL_CONFIG_SHEET_TITLE}!A2:H",
            )
        except GoogleSheetsHelperError as error:
            raise MonthlyFeesRepositoryError("Failed to fetch monthly financial config.") from error

        selected: dict[str, Any] | None = None
        for row in rows:
            item = self._row_to_record(row=row, headers=MONTHLY_FINANCIAL_CONFIG_HEADERS)
            if item.get("team_id") != team_id:
                continue
            if not self._parse_bool(item.get("is_active")):
                continue
            selected = item
        if selected is None:
            return None
        return {
            "team_id": selected.get("team_id"),
            "monthly_contribution_amount": self._parse_float(
                selected.get("monthly_contribution_amount")
            ),
            "court_monthly_amount": self._parse_float(selected.get("court_monthly_amount")),
            "training_weekdays": self._parse_weekdays(selected.get("training_weekdays")),
            "currency": selected.get("currency") or "BRL",
            "is_active": self._parse_bool(selected.get("is_active")),
            "created_at": selected.get("created_at"),
            "updated_at": selected.get("updated_at"),
        }

    def list_monthly_financial_people_config(
        self,
        *,
        spreadsheet_id: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        team_id: str,
    ) -> list[dict[str, Any]]:
        sheets_helper = self._build_sheets_helper(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )
        try:
            self._ensure_sheet_exists(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FINANCIAL_PEOPLE_CONFIG_SHEET_TITLE,
            )
            self._ensure_sheet_header(
                sheets_helper=sheets_helper,
                spreadsheet_id=spreadsheet_id,
                sheet_title=MONTHLY_FINANCIAL_PEOPLE_CONFIG_SHEET_TITLE,
                headers=MONTHLY_FINANCIAL_PEOPLE_CONFIG_HEADERS,
            )
            rows = sheets_helper.get_values(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{MONTHLY_FINANCIAL_PEOPLE_CONFIG_SHEET_TITLE}!A2:J",
            )
        except GoogleSheetsHelperError as error:
            raise MonthlyFeesRepositoryError("Failed to fetch monthly people config.") from error

        items: list[dict[str, Any]] = []
        for row in rows:
            item = self._row_to_record(row=row, headers=MONTHLY_FINANCIAL_PEOPLE_CONFIG_HEADERS)
            if item.get("team_id") != team_id:
                continue
            if not self._parse_bool(item.get("is_active")):
                continue
            items.append(
                {
                    "config_id": item.get("config_id"),
                    "team_id": item.get("team_id"),
                    "person_id": item.get("person_id"),
                    "person_name": item.get("person_name"),
                    "role": item.get("role"),
                    "amount_type": item.get("amount_type"),
                    "amount": self._parse_float(item.get("amount")),
                    "is_active": self._parse_bool(item.get("is_active")),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                }
            )
        return items

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
            raise MonthlyFeesRepositoryError(str(error)) from error
        return GoogleSheetsHelper(sheets_service=sheets_service)

    def _ensure_sheet_exists(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
        sheet_title: str,
    ) -> None:
        spreadsheet = sheets_helper.get_spreadsheet(
            spreadsheet_id=spreadsheet_id,
            fields="sheets(properties(title))",
        )
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties")
            if isinstance(properties, dict) and properties.get("title") == sheet_title:
                return
        sheets_helper.add_sheet(
            spreadsheet_id=spreadsheet_id,
            sheet_title=sheet_title,
        )

    def _ensure_sheet_header(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
        sheet_title: str,
        headers: list[str],
    ) -> None:
        current_header = sheets_helper.get_values(
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_title}!1:1",
        )
        if current_header:
            header_row = current_header[0]
            if len(header_row) >= len(headers):
                return
            for index in range(len(header_row), len(headers)):
                column = self._column_label(index + 1)
                sheets_helper.update_values(
                    spreadsheet_id=spreadsheet_id,
                    range_name=f"{sheet_title}!{column}1:{column}1",
                    values=[[headers[index]]],
                )
            return
        last_column = self._column_label(len(headers))
        sheets_helper.update_values(
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_title}!A1:{last_column}1",
            values=[headers],
        )

    def _get_sheet_headers(
        self,
        *,
        sheets_helper: GoogleSheetsHelper,
        spreadsheet_id: str,
        sheet_title: str,
        default_headers: list[str],
    ) -> list[str]:
        current_header = sheets_helper.get_values(
            spreadsheet_id=spreadsheet_id,
            range_name=f"{sheet_title}!1:1",
        )
        if not current_header:
            return list(default_headers)
        header_row = [str(value).strip() for value in current_header[0]]
        sanitized = [value for value in header_row if value]
        if not sanitized:
            return list(default_headers)
        return sanitized

    @staticmethod
    def _row_to_record(*, row: list[Any], headers: list[str]) -> dict[str, Any]:
        serialized = [str(value).strip() for value in row[: len(headers)]]
        if len(serialized) < len(headers):
            serialized.extend([""] * (len(headers) - len(serialized)))
        record = dict(zip(headers, serialized))
        for key, value in list(record.items()):
            if value == "":
                record[key] = None
        return record

    @staticmethod
    def _record_to_row(*, record: dict[str, Any], headers: list[str]) -> list[str]:
        row: list[str] = []
        for header in headers:
            value = record.get(header)
            if value is None:
                row.append("")
                continue
            enum_value = getattr(value, "value", None)
            if isinstance(enum_value, str):
                row.append(enum_value)
                continue
            row.append(str(value))
        return row

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if not isinstance(value, str):
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _parse_float(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return 0.0
            try:
                return float(cleaned.replace(",", "."))
            except ValueError:
                return 0.0
        return 0.0

    @staticmethod
    def _parse_weekdays(value: Any) -> list[int]:
        if isinstance(value, list):
            raw_items = value
        elif isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            normalized = cleaned.replace("[", "").replace("]", "").replace(";", ",")
            raw_items = [item.strip() for item in normalized.split(",")]
        else:
            return []

        weekday_aliases = {
            "MONDAY": 0,
            "TUESDAY": 1,
            "WEDNESDAY": 2,
            "THURSDAY": 3,
            "FRIDAY": 4,
            "SATURDAY": 5,
            "SUNDAY": 6,
            "MON": 0,
            "TUE": 1,
            "WED": 2,
            "THU": 3,
            "FRI": 4,
            "SAT": 5,
            "SUN": 6,
        }

        items: list[int] = []
        for item in raw_items:
            if isinstance(item, int):
                candidate = item
            elif isinstance(item, str):
                normalized = item.strip().upper()
                if not normalized:
                    continue
                if normalized in weekday_aliases:
                    candidate = weekday_aliases[normalized]
                else:
                    try:
                        candidate = int(normalized)
                    except ValueError:
                        continue
            else:
                continue
            if 0 <= candidate <= 6:
                items.append(candidate)
        return sorted(set(items))

    @staticmethod
    def _column_label(index: int) -> str:
        label = ""
        value = index
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            label = chr(ord("A") + remainder) + label
        return label

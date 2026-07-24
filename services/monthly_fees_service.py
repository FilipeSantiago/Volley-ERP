from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from repositories.google_connection_repository import (
    GoogleConnectionRepository,
    GoogleConnectionRepositoryError,
)
from repositories.monthly_fees_repository import (
    MonthlyFeesRepository,
    MonthlyFeesRepositoryError,
)
from repositories.organization_repository import (
    OrganizationRepository,
    OrganizationRepositoryError,
)
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import TeamNotFoundError
from services.security.authorization_service import AuthorizationService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)

MONTHLY_FEE_TAG_TO_DIRECTION = {
    "MONTHLY_CONTRIBUTION": "CREDIT",
    "COACH": "DEBIT",
    "COMMISSION": "DEBIT",
    "COURT": "DEBIT",
}
RECURRING_MONTHLY_FEE_SOURCE = "RECURRING_RULE"


class MonthlyFeesService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        organization_repository: OrganizationRepository,
        google_connection_repository: GoogleConnectionRepository,
        refresh_token_encryption_service: RefreshTokenEncryptionService,
        authorization_service: AuthorizationService,
        monthly_fees_repository: MonthlyFeesRepository,
    ) -> None:
        self._auth_config = auth_config
        self._organization_repository = organization_repository
        self._google_connection_repository = google_connection_repository
        self._refresh_token_encryption_service = refresh_token_encryption_service
        self._authorization_service = authorization_service
        self._monthly_fees_repository = monthly_fees_repository

    def list_monthly_fees(
        self,
        *,
        user_id: str,
        team_id: str,
        tag: str | None,
        athlete_id: str | None,
        include_inactive: bool,
    ) -> dict[str, Any]:
        context = self._resolve_team_context(
            user_id=user_id,
            team_id=team_id,
            permission="finance.read",
        )
        spreadsheet_id = context["spreadsheet_id"]
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"]
        )
        try:
            items = self._monthly_fees_repository.list_monthly_fee_entries(
                spreadsheet_id=spreadsheet_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )
        except MonthlyFeesRepositoryError as error:
            raise ValueError("Failed to list monthly fees entries.") from error

        normalized: list[dict[str, Any]] = []
        for item in items:
            normalized_item = self._normalize_monthly_fee_entry(item)
            if normalized_item.get("team_id") != context["team_id"]:
                continue
            if normalized_item.get("source") != RECURRING_MONTHLY_FEE_SOURCE:
                continue
            normalized.append(normalized_item)

        filtered = [
            item
            for item in normalized
            if self._matches_filters(
                item=item,
                tag=tag,
                athlete_id=athlete_id,
                include_inactive=include_inactive,
            )
        ]
        return {"items": filtered, "count": len(filtered)}

    def create_monthly_fee(
        self,
        *,
        user_id: str,
        team_id: str,
        tag: str,
        amount: float,
        currency: str | None,
        athlete_id: str | None,
        person_name: str | None,
        description: str | None,
    ) -> dict[str, Any]:
        context = self._resolve_team_context(
            user_id=user_id,
            team_id=team_id,
            permission="finance.manage",
        )
        spreadsheet_id = context["spreadsheet_id"]
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"]
        )

        try:
            existing_items = self._monthly_fees_repository.list_monthly_fee_entries(
                spreadsheet_id=spreadsheet_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )
        except MonthlyFeesRepositoryError as error:
            raise ValueError("Failed to fetch existing monthly fees entries.") from error

        normalized_team = context["team_id"]
        normalized_tag = str(tag or "").strip().upper()
        normalized_amount = round(float(amount), 2)
        if normalized_amount < 0:
            raise ValueError("amount must be greater than or equal to 0.")
        normalized_currency = self._normalize_currency(currency)
        normalized_athlete_id = self._normalize_optional_text(athlete_id)
        normalized_person_name = self._normalize_optional_text(person_name)
        normalized_description = self._normalize_optional_text(description)
        self._validate_target_fields(
            tag=normalized_tag,
            athlete_id=normalized_athlete_id,
            person_name=normalized_person_name,
        )

        existing_keys = {
            key
            for key in (
                self._monthly_fee_recurrence_key(self._normalize_monthly_fee_entry(item))
                for item in existing_items
            )
            if key is not None
        }

        now = _now_iso()
        fee_id = str(uuid4())
        candidate = {
            "fee_id": fee_id,
            "entry_id": fee_id,
            "org_id": context["org_id"],
            "team_id": normalized_team,
            "tag": normalized_tag,
            "direction": MONTHLY_FEE_TAG_TO_DIRECTION[normalized_tag],
            "amount": normalized_amount,
            "currency": normalized_currency,
            "athlete_id": normalized_athlete_id,
            "person_name": normalized_person_name,
            "description": normalized_description,
            "source": RECURRING_MONTHLY_FEE_SOURCE,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        candidate_key = self._monthly_fee_recurrence_key(candidate)
        if candidate_key is None:
            raise ValueError("Invalid recurring monthly fee data.")
        if candidate_key in existing_keys:
            raise ValueError("Recurring monthly fee already exists for the same target.")

        try:
            self._monthly_fees_repository.append_monthly_fee_entries(
                spreadsheet_id=spreadsheet_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                entries=[candidate],
            )
        except MonthlyFeesRepositoryError as error:
            raise ValueError("Failed to persist recurring monthly fee.") from error
        return self._normalize_monthly_fee_entry(candidate)

    def update_monthly_fee(
        self,
        *,
        user_id: str,
        team_id: str,
        fee_id: str,
        amount: float | None,
        currency: str | None,
        description: str | None,
    ) -> dict[str, Any] | None:
        context = self._resolve_team_context(
            user_id=user_id,
            team_id=team_id,
            permission="finance.manage",
        )
        spreadsheet_id = context["spreadsheet_id"]
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"]
        )
        if amount is not None and amount < 0:
            raise ValueError("amount must be greater than or equal to 0.")
        normalized_currency = self._normalize_currency(currency) if currency is not None else None
        normalized_description = self._normalize_optional_text(description)

        try:
            updated = self._monthly_fees_repository.update_monthly_fee_entry(
                spreadsheet_id=spreadsheet_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                entry_id=fee_id,
                expected_team_id=context["team_id"],
                expected_source=RECURRING_MONTHLY_FEE_SOURCE,
                amount=amount,
                currency=normalized_currency,
                description=normalized_description,
                is_active=None,
                updated_at=_now_iso(),
            )
        except MonthlyFeesRepositoryError as error:
            raise ValueError("Failed to update recurring monthly fee.") from error

        if updated is None:
            return None
        normalized = self._normalize_monthly_fee_entry(updated)
        if normalized.get("source") != RECURRING_MONTHLY_FEE_SOURCE:
            return None
        return normalized

    def soft_delete_monthly_fee(
        self,
        *,
        user_id: str,
        team_id: str,
        fee_id: str,
    ) -> dict[str, Any] | None:
        context = self._resolve_team_context(
            user_id=user_id,
            team_id=team_id,
            permission="finance.manage",
        )
        spreadsheet_id = context["spreadsheet_id"]
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"]
        )
        try:
            updated = self._monthly_fees_repository.update_monthly_fee_entry(
                spreadsheet_id=spreadsheet_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                entry_id=fee_id,
                expected_team_id=context["team_id"],
                expected_source=RECURRING_MONTHLY_FEE_SOURCE,
                amount=None,
                currency=None,
                description=None,
                is_active=False,
                updated_at=_now_iso(),
            )
        except MonthlyFeesRepositoryError as error:
            raise ValueError("Failed to deactivate recurring monthly fee.") from error
        if updated is None:
            return None
        normalized = self._normalize_monthly_fee_entry(updated)
        if normalized.get("source") != RECURRING_MONTHLY_FEE_SOURCE:
            return None
        return normalized

    def _resolve_team_context(
        self,
        *,
        user_id: str,
        team_id: str,
        permission: str,
    ) -> dict[str, Any]:
        if not isinstance(team_id, str) or not team_id.strip():
            raise ValueError("team_id is required.")
        normalized_team_id = team_id.strip()

        try:
            org_pointers = self._organization_repository.list_user_organizations(
                user_id=user_id
            )
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to resolve user organizations.") from error

        for pointer in org_pointers:
            if pointer.get("status") != "active":
                continue
            org_id = pointer.get("org_id")
            if not isinstance(org_id, str) or not org_id.strip():
                continue
            org_id = org_id.strip()
            try:
                team = self._organization_repository.get_team(
                    org_id=org_id,
                    team_id=normalized_team_id,
                )
            except OrganizationRepositoryError as error:
                raise ValueError("Failed to resolve team.") from error
            if team is None:
                continue

            self._authorization_service.require_team_permission(
                user_id=user_id,
                org_id=org_id,
                team_id=normalized_team_id,
                permission=permission,
            )
            organization = self._get_organization_or_raise(org_id=org_id)
            storage_owner_user_id = organization.get("storage_owner_user_id")
            if (
                not isinstance(storage_owner_user_id, str)
                or not storage_owner_user_id.strip()
            ):
                raise ValueError("Organization storage owner is missing.")
            spreadsheet_id = team.get("team_spreadsheet_id")
            if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
                raise ValueError("Failed to resolve team spreadsheet.")
            return {
                "org_id": org_id,
                "team_id": normalized_team_id,
                "team": team,
                "spreadsheet_id": spreadsheet_id.strip(),
                "storage_owner_user_id": storage_owner_user_id.strip(),
            }

        raise TeamNotFoundError("team_not_found")

    def _get_organization_or_raise(self, *, org_id: str) -> dict[str, Any]:
        try:
            organization = self._organization_repository.get_organization(org_id=org_id)
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to resolve organization.") from error
        if organization is None:
            raise ValueError("Organization not found.")
        return organization

    def _load_storage_owner_refresh_token(self, *, user_id: str) -> str:
        try:
            connection = self._google_connection_repository.get_by_user_id(user_id=user_id)
        except GoogleConnectionRepositoryError as error:
            raise ValueError("storage_owner_connection_missing") from error
        if connection is None:
            raise ValueError("storage_owner_connection_missing")
        encrypted_refresh_token = connection.get("encrypted_refresh_token")
        if not isinstance(encrypted_refresh_token, str) or not encrypted_refresh_token:
            raise ValueError("storage_owner_connection_missing")
        return self._refresh_token_encryption_service.decrypt(encrypted_refresh_token)

    def _normalize_monthly_fee_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        tag = str(entry.get("tag") or "").strip().upper()
        direction = str(entry.get("direction") or "").strip().upper()
        expected_direction = MONTHLY_FEE_TAG_TO_DIRECTION.get(tag)
        if expected_direction is None:
            raise ValueError("Invalid tag.")
        if direction and direction != expected_direction:
            raise ValueError("direction does not match tag.")

        amount_raw = entry.get("amount")
        if isinstance(amount_raw, str):
            try:
                amount = float(amount_raw.replace(",", "."))
            except ValueError:
                amount = 0.0
        elif isinstance(amount_raw, (int, float)):
            amount = float(amount_raw)
        else:
            amount = 0.0
        if amount < 0:
            raise ValueError("amount must be greater than or equal to 0.")

        source = str(entry.get("source") or "").strip().upper()
        if not source:
            source = RECURRING_MONTHLY_FEE_SOURCE

        fee_id = self._normalize_optional_text(entry.get("fee_id")) or self._normalize_optional_text(
            entry.get("entry_id")
        )
        if fee_id is None:
            raise ValueError("monthly fee id is required.")
        is_active = self._parse_bool(
            entry.get("is_active"),
            default=(source == RECURRING_MONTHLY_FEE_SOURCE),
        )

        return {
            "fee_id": fee_id,
            "org_id": str(entry.get("org_id") or ""),
            "team_id": str(entry.get("team_id") or ""),
            "tag": tag,
            "direction": expected_direction,
            "amount": round(amount, 2),
            "currency": self._normalize_currency(entry.get("currency")),
            "athlete_id": self._normalize_optional_text(entry.get("athlete_id")),
            "person_name": self._normalize_optional_text(entry.get("person_name")),
            "description": self._normalize_optional_text(entry.get("description")),
            "source": source,
            "is_active": is_active,
            "created_at": str(entry.get("created_at") or ""),
            "updated_at": str(entry.get("updated_at") or ""),
        }

    def _monthly_fee_recurrence_key(self, item: dict[str, Any]) -> str | None:
        source = str(item.get("source") or "").strip().upper()
        is_active = bool(item.get("is_active"))
        if source != RECURRING_MONTHLY_FEE_SOURCE or not is_active:
            return None

        team_id = self._normalize_optional_text(item.get("team_id"))
        tag = self._normalize_optional_text(item.get("tag"))
        if team_id is None or tag is None:
            return None
        tag = tag.upper()
        prefix = f"{team_id}|{tag}"
        if tag == "MONTHLY_CONTRIBUTION":
            athlete_id = self._normalize_optional_text(item.get("athlete_id"))
            if athlete_id is None:
                return None
            return f"{prefix}|athlete|{athlete_id}"
        if tag == "COACH":
            person_name = self._normalize_optional_text(item.get("person_name"))
            if person_name is not None:
                return f"{prefix}|person_name|{person_name.lower()}"
            return prefix
        if tag == "COMMISSION":
            person_name = self._normalize_optional_text(item.get("person_name"))
            if person_name is not None:
                return f"{prefix}|person_name|{person_name.lower()}"
            return None
        if tag == "COURT":
            return prefix
        return None

    def _matches_filters(
        self,
        *,
        item: dict[str, Any],
        tag: str | None,
        athlete_id: str | None,
        include_inactive: bool,
    ) -> bool:
        if not include_inactive and not bool(item.get("is_active")):
            return False
        if tag is not None and str(item.get("tag") or "") != tag:
            return False
        if athlete_id is not None and str(item.get("athlete_id") or "") != athlete_id:
            return False
        return True

    def _validate_target_fields(
        self,
        *,
        tag: str,
        athlete_id: str | None,
        person_name: str | None,
    ) -> None:
        if tag not in MONTHLY_FEE_TAG_TO_DIRECTION:
            raise ValueError("Invalid tag.")
        if tag == "MONTHLY_CONTRIBUTION":
            if athlete_id is None:
                raise ValueError("athlete_id is required for MONTHLY_CONTRIBUTION.")
            return
        if tag == "COACH":
            if athlete_id is not None:
                raise ValueError("athlete_id is not allowed for COACH.")
            return
        if tag == "COMMISSION":
            if athlete_id is not None:
                raise ValueError("athlete_id is not allowed for COMMISSION.")
            if person_name is None:
                raise ValueError("person_name is required for COMMISSION.")
            return
        if tag == "COURT":
            if athlete_id is not None or person_name is not None:
                raise ValueError("athlete_id/person_name are not allowed for COURT.")

    @staticmethod
    def _normalize_optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _normalize_currency(value: Any) -> str:
        normalized = str(value or "BRL").strip().upper()
        return normalized or "BRL"

    @staticmethod
    def _parse_bool(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if not cleaned:
                return default
            return cleaned in {"1", "true", "yes", "on"}
        return bool(value)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )

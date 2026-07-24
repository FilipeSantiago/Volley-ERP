import os
import re
from datetime import date
from typing import Any

from repositories.coach_repository import CoachRepository, CoachRepositoryError
from repositories.google_connection_repository import (
    GoogleConnectionRepository,
    GoogleConnectionRepositoryError,
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
from services.workspace_service import WorkspaceService

_FILENAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


class CoachService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        organization_repository: OrganizationRepository,
        google_connection_repository: GoogleConnectionRepository,
        coach_repository: CoachRepository,
        refresh_token_encryption_service: RefreshTokenEncryptionService,
        authorization_service: AuthorizationService,
        workspace_service: WorkspaceService,
    ) -> None:
        self._auth_config = auth_config
        self._organization_repository = organization_repository
        self._google_connection_repository = google_connection_repository
        self._coach_repository = coach_repository
        self._refresh_token_encryption_service = refresh_token_encryption_service
        self._authorization_service = authorization_service
        self._workspace_service = workspace_service

    def create_coach(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._authorization_service.require_org_role(
            user_id=user_id,
            org_id=org_id,
            allowed_roles={"OWNER", "ADMIN"},
        )
        normalized = self._normalize_coach_payload(payload, require_photo=True)
        context = self._resolve_team_context(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="players.manage",
        )
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"],
        )
        workspace = self._workspace_service.ensure_workspace_for_organization(org_id=org_id)
        images_folder_id = workspace.get("workspace_images_folder_id")
        if not isinstance(images_folder_id, str) or not images_folder_id.strip():
            raise ValueError("Organization workspace is not provisioned.")

        try:
            coach = self._coach_repository.upsert_team_coach(
                spreadsheet_id=context["spreadsheet_id"],
                team_id=team_id,
                images_folder_id=images_folder_id.strip(),
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                coach=normalized,
            )
        except CoachRepositoryError as error:
            raise ValueError("Failed to persist coach data.") from error
        return self._build_coach_response(
            org_id=org_id,
            team_id=team_id,
            spreadsheet_id=context["spreadsheet_id"],
            spreadsheet_url=context.get("spreadsheet_url"),
            coach=coach,
        )

    def update_coach(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        self._authorization_service.require_org_role(
            user_id=user_id,
            org_id=org_id,
            allowed_roles={"OWNER", "ADMIN"},
        )
        normalized = self._normalize_coach_payload(payload, require_photo=False)
        context = self._resolve_team_context(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="players.manage",
        )
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"],
        )
        try:
            existing = self._coach_repository.get_team_coach(
                spreadsheet_id=context["spreadsheet_id"],
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )
        except CoachRepositoryError as error:
            raise ValueError("Failed to resolve coach data.") from error
        if existing is None:
            return None

        workspace = self._workspace_service.ensure_workspace_for_organization(org_id=org_id)
        images_folder_id = workspace.get("workspace_images_folder_id")
        if not isinstance(images_folder_id, str) or not images_folder_id.strip():
            raise ValueError("Organization workspace is not provisioned.")

        try:
            coach = self._coach_repository.upsert_team_coach(
                spreadsheet_id=context["spreadsheet_id"],
                team_id=team_id,
                images_folder_id=images_folder_id.strip(),
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                coach=normalized,
            )
        except CoachRepositoryError as error:
            raise ValueError("Failed to persist coach data.") from error
        return self._build_coach_response(
            org_id=org_id,
            team_id=team_id,
            spreadsheet_id=context["spreadsheet_id"],
            spreadsheet_url=context.get("spreadsheet_url"),
            coach=coach,
        )

    def get_coach(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
    ) -> dict[str, Any] | None:
        context = self._resolve_team_context(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="players.read",
        )
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"],
        )
        try:
            coach = self._coach_repository.get_team_coach(
                spreadsheet_id=context["spreadsheet_id"],
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )
        except CoachRepositoryError as error:
            raise ValueError("Failed to resolve coach data.") from error
        if coach is None:
            return None
        return self._build_coach_response(
            org_id=org_id,
            team_id=team_id,
            spreadsheet_id=context["spreadsheet_id"],
            spreadsheet_url=context.get("spreadsheet_url"),
            coach=coach,
        )

    def get_coach_photo(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
    ) -> dict[str, Any] | None:
        context = self._resolve_team_context(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="players.read",
        )
        refresh_token = self._load_storage_owner_refresh_token(
            user_id=context["storage_owner_user_id"],
        )
        try:
            photo = self._coach_repository.get_team_coach_photo(
                spreadsheet_id=context["spreadsheet_id"],
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )
        except CoachRepositoryError as error:
            raise ValueError("Failed to fetch coach photo.") from error
        if photo is None:
            return None
        return {
            **photo,
            "org_id": org_id,
            "team_id": team_id,
        }

    def _resolve_team_context(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        permission: str,
    ) -> dict[str, Any]:
        self._authorization_service.require_team_permission(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission=permission,
        )
        organization = self._get_organization_or_raise(org_id=org_id)
        storage_owner_user_id = organization.get("storage_owner_user_id")
        if not isinstance(storage_owner_user_id, str) or not storage_owner_user_id.strip():
            raise ValueError("Organization storage owner is missing.")

        team = self._get_team_or_raise(org_id=org_id, team_id=team_id)
        spreadsheet_id = team.get("team_spreadsheet_id")
        if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
            raise ValueError("Failed to resolve team spreadsheet.")
        return {
            "organization": organization,
            "team": team,
            "spreadsheet_id": spreadsheet_id.strip(),
            "spreadsheet_url": team.get("team_spreadsheet_url"),
            "storage_owner_user_id": storage_owner_user_id.strip(),
        }

    def _get_organization_or_raise(self, *, org_id: str) -> dict[str, Any]:
        try:
            organization = self._organization_repository.get_organization(org_id=org_id)
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to resolve organization.") from error
        if organization is None:
            raise ValueError("Organization not found.")
        return organization

    def _get_team_or_raise(self, *, org_id: str, team_id: str) -> dict[str, Any]:
        try:
            team = self._organization_repository.get_team(org_id=org_id, team_id=team_id)
        except OrganizationRepositoryError as error:
            raise TeamNotFoundError("team_not_found") from error
        if team is None:
            raise TeamNotFoundError("team_not_found")
        return team

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

    def _build_coach_response(
        self,
        *,
        org_id: str,
        team_id: str,
        spreadsheet_id: str,
        spreadsheet_url: Any,
        coach: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "org_id": org_id,
            "team_id": team_id,
            "coach_sheet_id": spreadsheet_id,
            "coach_sheet_url": spreadsheet_url if isinstance(spreadsheet_url, str) else None,
            "full_name": coach.get("full_name"),
            "birthday": coach.get("birthday"),
            "cpf": coach.get("cpf"),
            "cellphone": coach.get("cellphone"),
            "tshirt_size": coach.get("tshirt_size"),
            "shorts_size": coach.get("shorts_size"),
            "position": coach.get("position"),
            "rg": coach.get("rg"),
            "email": coach.get("email"),
            "pix_key": coach.get("pix_key"),
            "photo_link": coach.get("photo_link"),
            "created_at": coach.get("created_at"),
            "updated_at": coach.get("updated_at"),
        }

    @staticmethod
    def _normalize_coach_payload(
        payload: dict[str, Any],
        *,
        require_photo: bool,
    ) -> dict[str, Any]:
        required_fields = ("full_name", "cpf", "cellphone", "position", "pix_key")
        optional_fields = ("tshirt_size", "shorts_size", "rg", "email")
        normalized_payload: dict[str, Any] = {}

        for field in required_fields:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required.")
            normalized_payload[field] = value.strip()

        birthday_value = payload.get("birthday")
        if isinstance(birthday_value, date):
            normalized_payload["birthday"] = birthday_value.isoformat()
        elif isinstance(birthday_value, str) and birthday_value.strip():
            normalized_payload["birthday"] = CoachService._normalize_birthday_string(
                birthday_value
            )
        else:
            raise ValueError("birthday is required.")

        for field in optional_fields:
            value = payload.get(field)
            if value is None:
                normalized_payload[field] = None
                continue
            if not isinstance(value, str):
                raise ValueError(f"{field} must be a string.")
            stripped = value.strip()
            normalized_payload[field] = stripped if stripped else None

        photo_content = payload.get("photo_content")
        photo_filename = payload.get("photo_filename")
        photo_mime_type = payload.get("photo_mime_type")
        has_photo_payload = any(
            payload.get(field) is not None
            for field in ("photo_content", "photo_filename", "photo_mime_type")
        )

        if require_photo or has_photo_payload:
            if not isinstance(photo_content, bytes) or len(photo_content) == 0:
                raise ValueError("photo is required and must be a non-empty file.")
            if not isinstance(photo_filename, str) or not photo_filename.strip():
                raise ValueError("photo filename is required.")
            if photo_mime_type is not None and not isinstance(photo_mime_type, str):
                raise ValueError("photo mimetype must be a string when provided.")

            normalized_payload["photo_content"] = photo_content
            normalized_payload["photo_filename"] = CoachService._secure_filename(
                photo_filename
            )
            if not normalized_payload["photo_filename"]:
                raise ValueError("photo must include a valid filename.")
            normalized_payload["photo_mime_type"] = (
                photo_mime_type.strip() if isinstance(photo_mime_type, str) else None
            )
        else:
            normalized_payload["photo_content"] = None
            normalized_payload["photo_filename"] = None
            normalized_payload["photo_mime_type"] = None

        return normalized_payload

    @staticmethod
    def _secure_filename(filename: str) -> str:
        normalized = filename.strip().replace("\\", "/")
        base_name = os.path.basename(normalized)
        sanitized = _FILENAME_SANITIZE_PATTERN.sub("_", base_name)
        return sanitized.strip("._")

    @staticmethod
    def _normalize_birthday_string(value: str) -> str:
        cleaned = value.strip()
        try:
            return date.fromisoformat(cleaned).isoformat()
        except ValueError:
            pass

        day_month_year = re.fullmatch(r"(\\d{2})/(\\d{2})/(\\d{4})", cleaned)
        if day_month_year is not None:
            day = int(day_month_year.group(1))
            month = int(day_month_year.group(2))
            year = int(day_month_year.group(3))
            return date(year=year, month=month, day=day).isoformat()

        raise ValueError("birthday must be a valid date.")

import os
import re
from datetime import date
from typing import Any

from repositories.google_connection_repository import (
    GoogleConnectionRepository,
    GoogleConnectionRepositoryError,
)
from repositories.organization_repository import (
    OrganizationRepository,
    OrganizationRepositoryError,
)
from repositories.team_workspace_repository import (
    TeamWorkspaceRepository,
    TeamWorkspaceRepositoryError,
)
from repositories.user_repository import UserRepository, UserRepositoryError
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import ForbiddenError, TeamNotFoundError
from services.security.authorization_service import AuthorizationService
from services.security.invite_service import InviteService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)
from services.workspace_service import WorkspaceService

TEAM_ASSIGNABLE_ROLES = {"TEAM_ADMIN", "COACH", "ASSISTANT", "PLAYER", "VIEWER"}
_FILENAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


class OrganizationTeamService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        organization_repository: OrganizationRepository,
        user_repository: UserRepository,
        google_connection_repository: GoogleConnectionRepository,
        team_workspace_repository: TeamWorkspaceRepository,
        refresh_token_encryption_service: RefreshTokenEncryptionService,
        workspace_service: WorkspaceService,
        authorization_service: AuthorizationService,
        invite_service: InviteService,
    ) -> None:
        self._auth_config = auth_config
        self._organization_repository = organization_repository
        self._user_repository = user_repository
        self._google_connection_repository = google_connection_repository
        self._team_workspace_repository = team_workspace_repository
        self._refresh_token_encryption_service = refresh_token_encryption_service
        self._workspace_service = workspace_service
        self._authorization_service = authorization_service
        self._invite_service = invite_service

    def create_team(self, *, user_id: str, org_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._authorization_service.require_org_permission(
            user_id=user_id,
            org_id=org_id,
            permission="teams.create",
        )
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required.")
        normalized_name = name.strip()

        category = payload.get("category")
        gender = payload.get("gender")
        category_value = category.strip() if isinstance(category, str) and category.strip() else None
        gender_value = gender.strip() if isinstance(gender, str) and gender.strip() else None

        try:
            team = self._organization_repository.create_team(
                org_id=org_id,
                name=normalized_name,
                category=category_value,
                gender=gender_value,
                status="active",
            )
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to create team.") from error

        organization = self._get_organization_or_raise(org_id=org_id)
        storage_owner_user_id = organization.get("storage_owner_user_id")
        if not isinstance(storage_owner_user_id, str) or not storage_owner_user_id.strip():
            raise ValueError("Organization storage owner is missing.")
        refresh_token = self._load_storage_owner_refresh_token(user_id=storage_owner_user_id)

        workspace = self._workspace_service.ensure_workspace_for_organization(org_id=org_id)
        sheets_folder_id = workspace.get("workspace_sheets_folder_id")
        if not isinstance(sheets_folder_id, str) or not sheets_folder_id.strip():
            raise ValueError("Organization workspace is not provisioned.")

        try:
            spreadsheet = self._team_workspace_repository.create_team_spreadsheet(
                team_id=team["team_id"],
                team_name=team.get("name"),
                sheets_folder_id=sheets_folder_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )
            team = self._organization_repository.update_team_spreadsheet(
                org_id=org_id,
                team_id=team["team_id"],
                spreadsheet_id=spreadsheet["spreadsheet_id"],
                spreadsheet_url=spreadsheet.get("spreadsheet_url"),
            )
        except (OrganizationRepositoryError, TeamWorkspaceRepositoryError) as error:
            raise ValueError("Failed to provision team spreadsheet.") from error

        return {
            "team_id": team["team_id"],
            "name": team.get("name"),
            "status": team.get("status"),
            "team_spreadsheet_id": team.get("team_spreadsheet_id"),
            "team_spreadsheet_url": team.get("team_spreadsheet_url"),
        }

    def create_athlete(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._authorization_service.require_team_permission(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="players.manage",
        )
        normalized = self._normalize_athlete_payload(payload)
        team = self._get_team_or_raise(org_id=org_id, team_id=team_id)
        organization = self._get_organization_or_raise(org_id=org_id)

        storage_owner_user_id = organization.get("storage_owner_user_id")
        if not isinstance(storage_owner_user_id, str) or not storage_owner_user_id.strip():
            raise ValueError("Organization storage owner is missing.")
        refresh_token = self._load_storage_owner_refresh_token(user_id=storage_owner_user_id)

        workspace = self._workspace_service.ensure_workspace_for_organization(org_id=org_id)
        sheets_folder_id = workspace.get("workspace_sheets_folder_id")
        images_folder_id = workspace.get("workspace_images_folder_id")
        if not isinstance(sheets_folder_id, str) or not sheets_folder_id.strip():
            raise ValueError("Organization workspace is not provisioned.")
        if not isinstance(images_folder_id, str) or not images_folder_id.strip():
            raise ValueError("Organization workspace is not provisioned.")

        spreadsheet_id = team.get("team_spreadsheet_id")
        spreadsheet_url = team.get("team_spreadsheet_url")
        if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
            try:
                created_sheet = self._team_workspace_repository.create_team_spreadsheet(
                    team_id=team_id,
                    team_name=team.get("name"),
                    sheets_folder_id=sheets_folder_id,
                    refresh_token=refresh_token,
                    client_id=self._auth_config.google_oauth_client_id,
                    client_secret=self._auth_config.google_oauth_client_secret,
                )
                team = self._organization_repository.update_team_spreadsheet(
                    org_id=org_id,
                    team_id=team_id,
                    spreadsheet_id=created_sheet["spreadsheet_id"],
                    spreadsheet_url=created_sheet.get("spreadsheet_url"),
                )
            except (TeamWorkspaceRepositoryError, OrganizationRepositoryError) as error:
                raise ValueError("Failed to provision team spreadsheet.") from error
            spreadsheet_id = team.get("team_spreadsheet_id")
            spreadsheet_url = team.get("team_spreadsheet_url")

        if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
            raise ValueError("Failed to resolve team spreadsheet.")

        try:
            athlete_result = self._team_workspace_repository.append_team_athlete(
                org_id=org_id,
                team_id=team_id,
                spreadsheet_id=spreadsheet_id,
                images_folder_id=images_folder_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                athlete=normalized,
            )
        except TeamWorkspaceRepositoryError as error:
            raise ValueError("Failed to persist athlete data.") from error

        return {
            "org_id": org_id,
            "team_id": team_id,
            "athletes_sheet_id": spreadsheet_id,
            "athletes_sheet_url": spreadsheet_url,
            "athlete_id": athlete_result.get("athlete_id"),
            "full_name": normalized["full_name"],
            "birthday": normalized["birthday"],
            "cpf": normalized["cpf"],
            "cellphone": normalized["cellphone"],
            "position": normalized["position"],
            "tshirt_size": normalized["tshirt_size"],
            "shorts_size": normalized["shorts_size"],
            "rg": normalized["rg"],
            "email": normalized["email"],
            "photo_link": athlete_result.get("photo_link"),
            "created_at": athlete_result.get("created_at"),
            "updated_at": athlete_result.get("updated_at"),
        }

    def update_athlete(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        self._authorization_service.require_team_permission(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="players.manage",
        )
        normalized = self._normalize_athlete_payload(
            payload,
            require_photo=False,
            require_athlete_id=True,
        )
        team = self._get_team_or_raise(org_id=org_id, team_id=team_id)
        organization = self._get_organization_or_raise(org_id=org_id)

        storage_owner_user_id = organization.get("storage_owner_user_id")
        if not isinstance(storage_owner_user_id, str) or not storage_owner_user_id.strip():
            raise ValueError("Organization storage owner is missing.")
        refresh_token = self._load_storage_owner_refresh_token(user_id=storage_owner_user_id)

        workspace = self._workspace_service.ensure_workspace_for_organization(org_id=org_id)
        images_folder_id = workspace.get("workspace_images_folder_id")

        spreadsheet_id = team.get("team_spreadsheet_id")
        spreadsheet_url = team.get("team_spreadsheet_url")
        if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
            raise ValueError("Failed to resolve team spreadsheet.")

        try:
            athlete_result = self._team_workspace_repository.update_team_athlete(
                org_id=org_id,
                team_id=team_id,
                spreadsheet_id=spreadsheet_id,
                images_folder_id=images_folder_id if isinstance(images_folder_id, str) else "",
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                athlete=normalized,
            )
        except TeamWorkspaceRepositoryError as error:
            raise ValueError("Failed to update athlete data.") from error

        if athlete_result is None:
            return None

        return {
            "org_id": org_id,
            "team_id": team_id,
            "athletes_sheet_id": spreadsheet_id,
            "athletes_sheet_url": spreadsheet_url,
            "athlete_id": athlete_result.get("athlete_id") or normalized["athlete_id"],
            "full_name": normalized["full_name"],
            "birthday": normalized["birthday"],
            "cpf": normalized["cpf"],
            "cellphone": normalized["cellphone"],
            "position": normalized["position"],
            "tshirt_size": normalized["tshirt_size"],
            "shorts_size": normalized["shorts_size"],
            "rg": normalized["rg"],
            "email": normalized["email"],
            "photo_link": athlete_result.get("photo_link"),
            "created_at": athlete_result.get("created_at"),
            "updated_at": athlete_result.get("updated_at"),
        }

    def list_athletes(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
    ) -> dict[str, Any]:
        self._authorization_service.require_team_permission(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="players.read",
        )
        team = self._get_team_or_raise(org_id=org_id, team_id=team_id)
        organization = self._get_organization_or_raise(org_id=org_id)

        storage_owner_user_id = organization.get("storage_owner_user_id")
        if not isinstance(storage_owner_user_id, str) or not storage_owner_user_id.strip():
            raise ValueError("Organization storage owner is missing.")
        refresh_token = self._load_storage_owner_refresh_token(user_id=storage_owner_user_id)

        spreadsheet_id = team.get("team_spreadsheet_id")
        spreadsheet_url = team.get("team_spreadsheet_url")
        if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
            return {
                "org_id": org_id,
                "team_id": team_id,
                "athletes_sheet_id": None,
                "athletes_sheet_url": None,
                "items": [],
                "count": 0,
            }

        try:
            athletes_data = self._team_workspace_repository.list_team_athletes(
                spreadsheet_id=spreadsheet_id,
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )
        except TeamWorkspaceRepositoryError as error:
            raise ValueError("Failed to fetch athletes data.") from error

        items = athletes_data["items"]
        return {
            "org_id": org_id,
            "team_id": team_id,
            "athletes_sheet_id": spreadsheet_id,
            "athletes_sheet_url": spreadsheet_url,
            "items": items,
            "count": len(items),
        }

    def get_athlete_photo_by_id(
        self,
        *,
        user_id: str,
        athlete_id: str,
    ) -> dict[str, Any] | None:
        normalized_athlete_id = athlete_id.strip()
        if not normalized_athlete_id:
            raise ValueError("athlete_id is required.")

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
                organization = self._get_organization_or_raise(org_id=org_id)
                storage_owner_user_id = organization.get("storage_owner_user_id")
                if (
                    not isinstance(storage_owner_user_id, str)
                    or not storage_owner_user_id.strip()
                ):
                    continue
                refresh_token = self._load_storage_owner_refresh_token(
                    user_id=storage_owner_user_id
                )
                team_records = self._list_accessible_teams_for_user_in_org(
                    user_id=user_id,
                    org_id=org_id,
                )
            except (ForbiddenError, ValueError, OrganizationRepositoryError):
                continue
            for team in team_records:
                team_id = team.get("team_id")
                spreadsheet_id = team.get("team_spreadsheet_id")
                if not isinstance(team_id, str) or not team_id.strip():
                    continue
                if not isinstance(spreadsheet_id, str) or not spreadsheet_id.strip():
                    continue

                try:
                    athlete_photo = self._team_workspace_repository.get_team_athlete_photo_by_id(
                        spreadsheet_id=spreadsheet_id,
                        athlete_id=normalized_athlete_id,
                        refresh_token=refresh_token,
                        client_id=self._auth_config.google_oauth_client_id,
                        client_secret=self._auth_config.google_oauth_client_secret,
                    )
                except TeamWorkspaceRepositoryError:
                    continue
                if athlete_photo is None:
                    continue

                return {
                    "athlete_id": athlete_photo["athlete_id"],
                    "content": athlete_photo["content"],
                    "mime_type": athlete_photo.get("mime_type"),
                    "file_name": athlete_photo.get("file_name"),
                    "full_name": athlete_photo.get("full_name"),
                    "org_id": org_id,
                    "team_id": team_id,
                }

        return None

    def list_teams(self, *, user_id: str, org_id: str) -> dict[str, Any]:
        self._authorization_service.require_org_member(user_id=user_id, org_id=org_id)
        can_access_all = self._authorization_service.can_access_all_teams(
            user_id=user_id,
            org_id=org_id,
        )
        try:
            if can_access_all:
                teams = self._organization_repository.list_teams_for_org(org_id=org_id)
                items = [
                    {
                        "team_id": team.get("team_id"),
                        "name": team.get("name"),
                        "category": team.get("category"),
                        "gender": team.get("gender"),
                        "status": team.get("status"),
                        "team_role": "ORG_ADMIN",
                        "team_spreadsheet_id": team.get("team_spreadsheet_id"),
                        "team_spreadsheet_url": team.get("team_spreadsheet_url"),
                    }
                    for team in teams
                    if team.get("status") == "active"
                ]
            else:
                pointers = self._organization_repository.list_user_team_pointers(
                    user_id=user_id,
                    org_id=org_id,
                )
                items = [
                    {
                        "team_id": pointer.get("team_id"),
                        "name": pointer.get("team_name"),
                        "status": pointer.get("status"),
                        "team_role": pointer.get("team_role"),
                    }
                    for pointer in pointers
                    if pointer.get("status") == "active"
                ]
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to list teams.") from error
        return {"items": items, "count": len(items)}

    def _list_accessible_teams_for_user_in_org(
        self,
        *,
        user_id: str,
        org_id: str,
    ) -> list[dict[str, Any]]:
        can_access_all = self._authorization_service.can_access_all_teams(
            user_id=user_id,
            org_id=org_id,
        )
        if can_access_all:
            teams = self._organization_repository.list_teams_for_org(org_id=org_id)
            return [team for team in teams if team.get("status") == "active"]

        pointers = self._organization_repository.list_user_team_pointers(
            user_id=user_id,
            org_id=org_id,
        )
        teams: list[dict[str, Any]] = []
        for pointer in pointers:
            if pointer.get("status") != "active":
                continue
            team_id = pointer.get("team_id")
            if not isinstance(team_id, str) or not team_id.strip():
                continue
            team = self._organization_repository.get_team(org_id=org_id, team_id=team_id)
            if team is None or team.get("status") != "active":
                continue
            teams.append(team)
        return teams

    def get_team(self, *, user_id: str, org_id: str, team_id: str) -> dict[str, Any]:
        self._authorization_service.require_team_permission(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="teams.read",
        )
        try:
            team = self._organization_repository.get_team(org_id=org_id, team_id=team_id)
        except OrganizationRepositoryError as error:
            raise TeamNotFoundError("team_not_found") from error
        if team is None:
            raise TeamNotFoundError("team_not_found")
        return {
            "team_id": team["team_id"],
            "name": team.get("name"),
            "category": team.get("category"),
            "gender": team.get("gender"),
            "status": team.get("status"),
            "team_spreadsheet_id": team.get("team_spreadsheet_id"),
            "team_spreadsheet_url": team.get("team_spreadsheet_url"),
        }

    def add_team_member(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._authorization_service.require_team_permission(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="team.members.manage",
        )
        email = payload.get("email")
        team_role = payload.get("team_role")
        if not isinstance(email, str) or not email.strip():
            raise ValueError("email is required.")
        if not isinstance(team_role, str) or team_role not in TEAM_ASSIGNABLE_ROLES:
            raise ValueError("Invalid team_role.")

        normalized_email = email.strip().lower()
        existing_user = self._find_user_by_email(email=normalized_email)
        if existing_user is None:
            invite = self._invite_service.create_invite(
                user_id=user_id,
                org_id=org_id,
                payload={
                    "email": normalized_email,
                    "team_id": team_id,
                    "team_role": team_role,
                },
            )
            return {"status": "invited", **invite}

        try:
            org_member = self._organization_repository.get_org_member(
                org_id=org_id,
                user_id=existing_user["user_id"],
            )
            if org_member is None:
                self._organization_repository.upsert_org_member_and_pointer(
                    org_id=org_id,
                    user_id=existing_user["user_id"],
                    email=existing_user.get("email"),
                    org_role="MEMBER",
                    status="active",
                )
            team_member = self._organization_repository.upsert_team_member_and_pointer(
                org_id=org_id,
                team_id=team_id,
                user_id=existing_user["user_id"],
                email=existing_user.get("email"),
                team_role=team_role,
                status="active",
            )
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to add team member.") from error

        return {
            "status": "ok",
            "team_id": team_id,
            "user_id": team_member["user_id"],
            "team_role": team_member["team_role"],
        }

    def list_team_members(self, *, user_id: str, org_id: str, team_id: str) -> dict[str, Any]:
        self._authorization_service.require_team_permission(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
            permission="team.members.read",
        )
        try:
            members = self._organization_repository.list_team_members(
                org_id=org_id,
                team_id=team_id,
            )
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to list team members.") from error

        items = [
            {
                "user_id": member.get("user_id"),
                "email": member.get("email"),
                "team_role": member.get("team_role"),
                "status": member.get("status"),
            }
            for member in members
        ]
        return {"items": items, "count": len(items)}

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

    def _find_user_by_email(self, *, email: str) -> dict[str, Any] | None:
        try:
            return self._user_repository.get_by_email(email=email)
        except UserRepositoryError as error:
            raise ValueError("Failed to resolve user by email.") from error

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

    @staticmethod
    def _normalize_athlete_payload(
        payload: dict[str, Any],
        *,
        require_photo: bool = True,
        require_athlete_id: bool = False,
    ) -> dict[str, Any]:
        required_fields = ("full_name", "cpf", "cellphone", "position")
        optional_fields = ("tshirt_size", "shorts_size", "rg", "email")
        normalized_payload: dict[str, Any] = {}

        if require_athlete_id:
            athlete_id = payload.get("athlete_id")
            if not isinstance(athlete_id, str) or not athlete_id.strip():
                raise ValueError("athlete_id is required.")
            normalized_payload["athlete_id"] = athlete_id.strip()

        for field in required_fields:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required.")
            normalized_payload[field] = value.strip()

        birthday_value = payload.get("birthday")
        if isinstance(birthday_value, date):
            normalized_payload["birthday"] = birthday_value.isoformat()
        elif isinstance(birthday_value, str) and birthday_value.strip():
            normalized_payload["birthday"] = OrganizationTeamService._normalize_birthday_string(
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
            normalized_payload["photo_filename"] = OrganizationTeamService._secure_filename(
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

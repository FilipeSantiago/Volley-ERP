from typing import Any

from repositories.google_connection_repository import (
    GoogleConnectionRepository,
    GoogleConnectionRepositoryError,
)
from repositories.organization_repository import (
    OrganizationRepository,
    OrganizationRepositoryError,
)
from repositories.user_repository import UserRepository, UserRepositoryError
from services.security.auth_exceptions import (
    OrganizationNotFoundError,
    StorageOwnerConnectionMissingError,
)
from services.security.authorization_service import AuthorizationService
from services.workspace_service import WorkspaceService


class OrganizationService:
    def __init__(
        self,
        *,
        organization_repository: OrganizationRepository,
        user_repository: UserRepository,
        google_connection_repository: GoogleConnectionRepository,
        authorization_service: AuthorizationService,
        workspace_service: WorkspaceService,
    ) -> None:
        self._organization_repository = organization_repository
        self._user_repository = user_repository
        self._google_connection_repository = google_connection_repository
        self._authorization_service = authorization_service
        self._workspace_service = workspace_service

    def create_organization(self, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name is required.")
        normalized_name = name.strip()

        self._require_google_connection(user_id=user_id)
        owner_email = self._resolve_user_email(user_id=user_id)

        try:
            organization = self._organization_repository.create_organization_with_owner(
                name=normalized_name,
                owner_user_id=user_id,
                owner_email=owner_email,
            )
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to create organization.") from error

        workspace = self._workspace_service.provision_workspace_for_new_organization(
            org_id=organization["org_id"],
            storage_owner_user_id=user_id,
        )
        return {
            "org_id": organization["org_id"],
            "name": organization["name"],
            "org_role": "OWNER",
            "workspace_status": "provisioned",
            "workspace_root_folder_id": workspace["workspace_root_folder_id"],
            "workspace_sheets_folder_id": workspace["workspace_sheets_folder_id"],
            "workspace_images_folder_id": workspace["workspace_images_folder_id"],
            "workspace_exports_folder_id": workspace["workspace_exports_folder_id"],
        }

    def list_organizations(self, *, user_id: str) -> list[dict[str, Any]]:
        try:
            pointers = self._organization_repository.list_user_organizations(user_id=user_id)
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to list organizations.") from error

        items: list[dict[str, Any]] = []
        for pointer in pointers:
            org_id = pointer.get("org_id")
            if not isinstance(org_id, str):
                continue
            if pointer.get("status") != "active":
                continue
            org_role = pointer.get("org_role")
            can_access_all_teams = org_role in {"OWNER", "ADMIN"}
            teams = self._list_visible_teams_for_user(
                user_id=user_id,
                org_id=org_id,
                can_access_all_teams=can_access_all_teams,
            )
            items.append(
                {
                    "org_id": org_id,
                    "name": pointer.get("org_name"),
                    "org_role": org_role,
                    "status": pointer.get("status"),
                    "can_access_all_teams": can_access_all_teams,
                    "teams": teams,
                }
            )
        return items

    def get_organization(self, *, user_id: str, org_id: str) -> dict[str, Any]:
        membership = self._authorization_service.require_org_member(
            user_id=user_id,
            org_id=org_id,
        )
        organization = self._get_organization_or_raise(org_id=org_id)
        can_access_all_teams = membership.get("org_role") in {"OWNER", "ADMIN"}
        teams = self._list_visible_teams_for_user(
            user_id=user_id,
            org_id=org_id,
            can_access_all_teams=can_access_all_teams,
        )
        return {
            "org_id": organization["org_id"],
            "name": organization.get("name"),
            "org_role": membership.get("org_role"),
            "status": membership.get("status"),
            "can_access_all_teams": can_access_all_teams,
            "teams": teams,
        }

    def ensure_workspace(self, *, user_id: str, org_id: str) -> dict[str, Any]:
        self._authorization_service.require_org_permission(
            user_id=user_id,
            org_id=org_id,
            permission="workspace.ensure",
        )
        workspace = self._workspace_service.ensure_workspace_for_organization(org_id=org_id)
        return {
            "status": "ok",
            "org_id": org_id,
            "workspace_root_folder_id": workspace["workspace_root_folder_id"],
            "workspace_sheets_folder_id": workspace["workspace_sheets_folder_id"],
            "workspace_images_folder_id": workspace["workspace_images_folder_id"],
            "workspace_exports_folder_id": workspace["workspace_exports_folder_id"],
        }

    def list_members(self, *, user_id: str, org_id: str) -> dict[str, Any]:
        self._authorization_service.require_org_permission(
            user_id=user_id,
            org_id=org_id,
            permission="members.read",
        )
        try:
            members = self._organization_repository.list_org_members(org_id=org_id)
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to list organization members.") from error

        items = [
            {
                "user_id": member.get("user_id"),
                "email": member.get("email"),
                "org_role": member.get("org_role"),
                "status": member.get("status"),
            }
            for member in members
        ]
        return {"items": items, "count": len(items)}

    def remove_member(self, *, requester_user_id: str, org_id: str, target_user_id: str) -> dict[str, Any]:
        self._authorization_service.require_org_permission(
            user_id=requester_user_id,
            org_id=org_id,
            permission="members.remove",
        )
        try:
            members = self._organization_repository.list_org_members(org_id=org_id)
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to load organization members.") from error
        active_owners = [
            member
            for member in members
            if member.get("status") == "active" and member.get("org_role") == "OWNER"
        ]
        target = next((member for member in members if member.get("user_id") == target_user_id), None)
        if target is None:
            raise ValueError("Member not found.")
        if target.get("org_role") == "OWNER" and len(active_owners) <= 1:
            raise ValueError("Cannot remove the only OWNER.")

        try:
            updated = self._organization_repository.set_org_member_status(
                org_id=org_id,
                user_id=target_user_id,
                status="inactive",
            )
            self._deactivate_team_memberships_for_user(
                org_id=org_id,
                user_id=target_user_id,
            )
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to remove organization member.") from error
        return {
            "status": "ok",
            "org_id": org_id,
            "user_id": updated.get("user_id"),
            "member_status": updated.get("status"),
        }

    def _list_visible_teams_for_user(
        self,
        *,
        user_id: str,
        org_id: str,
        can_access_all_teams: bool,
    ) -> list[dict[str, Any]]:
        try:
            if can_access_all_teams:
                teams = self._organization_repository.list_teams_for_org(org_id=org_id)
                return [
                    {
                        "team_id": team.get("team_id"),
                        "name": team.get("name"),
                        "team_role": "ORG_ADMIN",
                        "status": team.get("status"),
                    }
                    for team in teams
                    if team.get("status") == "active"
                ]
            pointers = self._organization_repository.list_user_team_pointers(
                user_id=user_id,
                org_id=org_id,
            )
        except OrganizationRepositoryError as error:
            raise ValueError("Failed to load organization teams.") from error

        return [
            {
                "team_id": pointer.get("team_id"),
                "name": pointer.get("team_name"),
                "team_role": pointer.get("team_role"),
                "status": pointer.get("status"),
            }
            for pointer in pointers
            if pointer.get("status") == "active"
        ]

    def _get_organization_or_raise(self, *, org_id: str) -> dict[str, Any]:
        try:
            organization = self._organization_repository.get_organization(org_id=org_id)
        except OrganizationRepositoryError as error:
            raise OrganizationNotFoundError("organization_not_found") from error
        if organization is None:
            raise OrganizationNotFoundError("organization_not_found")
        return organization

    def _require_google_connection(self, *, user_id: str) -> None:
        try:
            connection = self._google_connection_repository.get_by_user_id(user_id=user_id)
        except GoogleConnectionRepositoryError as error:
            raise StorageOwnerConnectionMissingError(
                "storage_owner_connection_missing"
            ) from error

        if connection is None or not isinstance(
            connection.get("encrypted_refresh_token"), str
        ):
            raise StorageOwnerConnectionMissingError("storage_owner_connection_missing")
        scopes = connection.get("scopes")
        if not isinstance(scopes, list):
            raise StorageOwnerConnectionMissingError("storage_owner_connection_missing")
        required_scopes = {
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/spreadsheets",
        }
        if not required_scopes.issubset(set(scopes)):
            raise StorageOwnerConnectionMissingError("storage_owner_connection_missing")

    def _resolve_user_email(self, *, user_id: str) -> str | None:
        try:
            user = self._user_repository.get_by_user_id(user_id=user_id)
        except UserRepositoryError:
            return None
        if user is None:
            return None
        email = user.get("email")
        if isinstance(email, str):
            return email
        return None

    def _deactivate_team_memberships_for_user(self, *, org_id: str, user_id: str) -> None:
        pointers = self._organization_repository.list_user_team_pointers(
            user_id=user_id,
            org_id=org_id,
        )
        for pointer in pointers:
            team_id = pointer.get("team_id")
            if not isinstance(team_id, str):
                continue
            self._organization_repository.set_team_member_status(
                org_id=org_id,
                team_id=team_id,
                user_id=user_id,
                status="inactive",
            )
            self._organization_repository.remove_user_team_pointer(
                user_id=user_id,
                org_id=org_id,
                team_id=team_id,
            )

from typing import Any

from repositories.organization_repository import (
    OrganizationRepository,
    OrganizationRepositoryError,
)
from services.security.auth_exceptions import (
    ForbiddenError,
    OrganizationNotFoundError,
    TeamNotFoundError,
)

ORG_ROLES_WITH_ALL_TEAM_ACCESS = {"OWNER", "ADMIN"}

ORG_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "OWNER": {"*"},
    "ADMIN": {
        "org.read",
        "org.manage",
        "workspace.ensure",
        "members.read",
        "members.invite",
        "members.remove",
        "teams.read",
        "teams.create",
        "teams.manage",
        "team.members.read",
        "team.members.manage",
        "players.read",
        "players.manage",
        "matches.read",
        "matches.manage",
        "finance.read",
        "finance.manage",
        "data.read",
        "data.write",
    },
    "MEMBER": {"org.read", "teams.read"},
}

TEAM_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "TEAM_ADMIN": {
        "teams.read",
        "team.members.read",
        "team.members.manage",
        "players.read",
        "players.manage",
        "matches.read",
        "matches.manage",
        "finance.read",
        "finance.manage",
        "data.read",
        "data.write",
    },
    "COACH": {
        "teams.read",
        "team.members.read",
        "players.read",
        "players.manage",
        "matches.read",
        "matches.manage",
        "data.read",
        "data.write",
    },
    "ASSISTANT": {
        "teams.read",
        "players.read",
        "matches.read",
        "matches.manage",
        "data.read",
    },
    "PLAYER": {"teams.read", "players.read", "matches.read", "data.read"},
    "VIEWER": {"teams.read", "players.read", "matches.read", "data.read"},
}


class AuthorizationService:
    def __init__(self, *, organization_repository: OrganizationRepository) -> None:
        self._organization_repository = organization_repository

    def require_org_member(self, *, user_id: str, org_id: str) -> dict[str, Any]:
        self._ensure_org_exists(org_id=org_id)
        try:
            membership = self._organization_repository.get_org_member(
                org_id=org_id,
                user_id=user_id,
            )
        except OrganizationRepositoryError as error:
            raise ForbiddenError("not_org_member") from error

        if membership is None or membership.get("status") != "active":
            raise ForbiddenError("not_org_member")
        return membership

    def require_org_role(
        self,
        *,
        user_id: str,
        org_id: str,
        allowed_roles: set[str],
    ) -> dict[str, Any]:
        membership = self.require_org_member(user_id=user_id, org_id=org_id)
        if membership.get("org_role") not in allowed_roles:
            raise ForbiddenError("insufficient_org_role")
        return membership

    def require_org_permission(
        self,
        *,
        user_id: str,
        org_id: str,
        permission: str,
    ) -> dict[str, Any]:
        membership = self.require_org_member(user_id=user_id, org_id=org_id)
        role = membership.get("org_role")
        allowed_permissions = ORG_ROLE_PERMISSIONS.get(role or "", set())
        if "*" in allowed_permissions or permission in allowed_permissions:
            return membership
        raise ForbiddenError("insufficient_org_role")

    def require_team_member(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
    ) -> dict[str, Any]:
        org_membership = self.require_org_member(user_id=user_id, org_id=org_id)
        if org_membership.get("org_role") in ORG_ROLES_WITH_ALL_TEAM_ACCESS:
            return {
                "user_id": user_id,
                "team_role": "ORG_ADMIN_BYPASS",
                "status": "active",
            }

        self._ensure_team_exists(org_id=org_id, team_id=team_id)
        try:
            team_membership = self._organization_repository.get_team_member(
                org_id=org_id,
                team_id=team_id,
                user_id=user_id,
            )
        except OrganizationRepositoryError as error:
            raise ForbiddenError("not_team_member") from error

        if team_membership is None or team_membership.get("status") != "active":
            raise ForbiddenError("not_team_member")
        return team_membership

    def require_team_role(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        allowed_roles: set[str],
    ) -> dict[str, Any]:
        org_membership = self.require_org_member(user_id=user_id, org_id=org_id)
        if org_membership.get("org_role") in ORG_ROLES_WITH_ALL_TEAM_ACCESS:
            return {
                "user_id": user_id,
                "team_role": "ORG_ADMIN_BYPASS",
                "status": "active",
            }

        team_membership = self.require_team_member(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
        )
        if team_membership.get("team_role") not in allowed_roles:
            raise ForbiddenError("insufficient_team_role")
        return team_membership

    def require_team_permission(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        permission: str,
    ) -> dict[str, Any]:
        org_membership = self.require_org_member(user_id=user_id, org_id=org_id)
        org_role = org_membership.get("org_role")
        org_permissions = ORG_ROLE_PERMISSIONS.get(org_role or "", set())
        if "*" in org_permissions or permission in org_permissions:
            return {
                "user_id": user_id,
                "team_role": "ORG_ADMIN_BYPASS",
                "status": "active",
            }

        team_membership = self.require_team_member(
            user_id=user_id,
            org_id=org_id,
            team_id=team_id,
        )
        team_role = team_membership.get("team_role")
        team_permissions = TEAM_ROLE_PERMISSIONS.get(team_role or "", set())
        if permission not in team_permissions:
            raise ForbiddenError("insufficient_team_role")
        return team_membership

    def can_access_all_teams(self, *, user_id: str, org_id: str) -> bool:
        membership = self.require_org_member(user_id=user_id, org_id=org_id)
        return membership.get("org_role") in ORG_ROLES_WITH_ALL_TEAM_ACCESS

    def _ensure_org_exists(self, *, org_id: str) -> None:
        try:
            organization = self._organization_repository.get_organization(org_id=org_id)
        except OrganizationRepositoryError as error:
            raise OrganizationNotFoundError("organization_not_found") from error

        if organization is None:
            raise OrganizationNotFoundError("organization_not_found")

    def _ensure_team_exists(self, *, org_id: str, team_id: str) -> None:
        try:
            team = self._organization_repository.get_team(org_id=org_id, team_id=team_id)
        except OrganizationRepositoryError as error:
            raise TeamNotFoundError("team_not_found") from error
        if team is None:
            raise TeamNotFoundError("team_not_found")

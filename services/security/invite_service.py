from datetime import datetime, timedelta, timezone
from typing import Any

from repositories.invite_repository import InviteRepository, InviteRepositoryError
from repositories.organization_repository import (
    OrganizationRepository,
    OrganizationRepositoryError,
)
from repositories.user_repository import UserRepository, UserRepositoryError
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import (
    ForbiddenError,
    InviteAlreadyAcceptedError,
    InviteEmailMismatchError,
    InviteExpiredError,
    InviteNotFoundError,
)
from services.security.authorization_service import AuthorizationService
from services.security.invite_token_service import InviteTokenService

TEAM_ROLES = {"TEAM_ADMIN", "COACH", "ASSISTANT", "PLAYER", "VIEWER"}
ORG_ROLES = {"OWNER", "ADMIN", "MEMBER"}


class InviteService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        invite_repository: InviteRepository,
        organization_repository: OrganizationRepository,
        user_repository: UserRepository,
        authorization_service: AuthorizationService,
        invite_token_service: InviteTokenService,
    ) -> None:
        self._auth_config = auth_config
        self._invite_repository = invite_repository
        self._organization_repository = organization_repository
        self._user_repository = user_repository
        self._authorization_service = authorization_service
        self._invite_token_service = invite_token_service

    def create_invite(
        self,
        *,
        user_id: str,
        org_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        email = payload.get("email")
        if not isinstance(email, str) or not email.strip():
            raise ValueError("email is required.")
        invited_email = email.strip().lower()
        org_role = payload.get("org_role")
        team_id = payload.get("team_id")
        team_role = payload.get("team_role")

        scope = self._resolve_scope(
            org_role=org_role,
            team_id=team_id,
            team_role=team_role,
        )
        requester = self._authorization_service.require_org_member(
            user_id=user_id,
            org_id=org_id,
        )
        requester_org_role = requester.get("org_role")
        if scope in {"org", "org_and_team"}:
            if not isinstance(org_role, str) or org_role not in ORG_ROLES:
                raise ValueError("Invalid org_role.")
            self._validate_org_role_assignment(
                requester_org_role=requester_org_role,
                requested_org_role=org_role,
            )
        if scope in {"team", "org_and_team"}:
            if not isinstance(team_id, str) or not team_id.strip():
                raise ValueError("team_id is required for team-scoped invite.")
            if not isinstance(team_role, str) or team_role not in TEAM_ROLES:
                raise ValueError("Invalid team_role.")
            self._validate_team_invite_permission(
                requester_user_id=user_id,
                requester_org_role=requester_org_role,
                org_id=org_id,
                team_id=team_id.strip(),
                requested_team_role=team_role,
            )

        token = self._invite_token_service.generate_token()
        token_hash = self._invite_token_service.hash_token(token=token)
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=self._auth_config.invite_token_ttl_seconds)
        ).replace(microsecond=0)
        expires_at_iso = expires_at.isoformat().replace("+00:00", "Z")

        try:
            self._invite_repository.revoke_pending_invites_for_scope(
                org_id=org_id,
                invited_email=invited_email,
                scope=scope,
                team_id=team_id.strip() if isinstance(team_id, str) else None,
            )
            invite = self._invite_repository.create_invite(
                org_id=org_id,
                invited_email=invited_email,
                scope=scope,
                org_role=org_role if isinstance(org_role, str) else None,
                team_id=team_id.strip() if isinstance(team_id, str) else None,
                team_role=team_role if isinstance(team_role, str) else None,
                token_hash=token_hash,
                expires_at=expires_at_iso,
                invited_by_user_id=user_id,
            )
        except InviteRepositoryError as error:
            raise ValueError("Failed to create invite.") from error

        base_url = self._auth_config.app_public_base_url.rstrip("/")
        invite_url = f"{base_url}/invite/accept?token={token}"
        return {
            "invite_id": invite["invite_id"],
            "invite_url": invite_url,
            "expires_at": expires_at_iso,
        }

    def accept_invite(self, *, user_id: str, token: str) -> dict[str, Any]:
        normalized_token = token.strip()
        if not normalized_token:
            raise InviteNotFoundError("invite_not_found")

        token_hash = self._invite_token_service.hash_token(token=normalized_token)
        try:
            invite = self._invite_repository.find_invite_by_token_hash(
                token_hash=token_hash,
                only_pending=False,
            )
        except InviteRepositoryError as error:
            raise InviteNotFoundError("invite_not_found") from error

        if invite is None:
            raise InviteNotFoundError("invite_not_found")

        status = invite.get("status")
        if status == "accepted":
            raise InviteAlreadyAcceptedError("invite_already_accepted")
        if status != "pending":
            raise InviteNotFoundError("invite_not_found")

        expires_at = _parse_iso_datetime(invite.get("expires_at"))
        if expires_at is None or expires_at <= datetime.now(timezone.utc):
            raise InviteExpiredError("invite_expired")

        user = self._get_user(user_id=user_id)
        user_email = (user.get("email") or "").strip().lower()
        invited_email = (invite.get("invited_email") or "").strip().lower()
        if not user_email or user_email != invited_email:
            raise InviteEmailMismatchError("invite_email_mismatch")

        org_id = invite.get("org_id")
        if not isinstance(org_id, str) or not org_id:
            raise InviteNotFoundError("invite_not_found")

        org_role_result: str | None = None
        team_id_result: str | None = None
        team_role_result: str | None = None

        scope = invite.get("scope")
        if scope in {"org", "org_and_team"}:
            org_role_value = invite.get("org_role")
            if isinstance(org_role_value, str):
                try:
                    self._organization_repository.upsert_org_member_and_pointer(
                        org_id=org_id,
                        user_id=user_id,
                        email=user.get("email"),
                        org_role=org_role_value,
                        status="active",
                    )
                except OrganizationRepositoryError as error:
                    raise ValueError("Failed to create organization membership.") from error
                org_role_result = org_role_value

        if scope in {"team", "org_and_team"}:
            team_id_value = invite.get("team_id")
            team_role_value = invite.get("team_role")
            if not isinstance(team_id_value, str) or not isinstance(team_role_value, str):
                raise InviteNotFoundError("invite_not_found")

            try:
                existing_org_member = self._organization_repository.get_org_member(
                    org_id=org_id,
                    user_id=user_id,
                )
                if existing_org_member is None or existing_org_member.get("status") != "active":
                    default_org_role = existing_org_member.get("org_role") if existing_org_member else None
                    if not isinstance(default_org_role, str):
                        default_org_role = "MEMBER"
                    self._organization_repository.upsert_org_member_and_pointer(
                        org_id=org_id,
                        user_id=user_id,
                        email=user.get("email"),
                        org_role=default_org_role,
                        status="active",
                    )
                    org_role_result = org_role_result or default_org_role

                self._organization_repository.upsert_team_member_and_pointer(
                    org_id=org_id,
                    team_id=team_id_value,
                    user_id=user_id,
                    email=user.get("email"),
                    team_role=team_role_value,
                    status="active",
                )
            except OrganizationRepositoryError as error:
                raise ValueError("Failed to create team membership.") from error
            team_id_result = team_id_value
            team_role_result = team_role_value

        try:
            self._invite_repository.mark_invite_accepted(
                org_id=org_id,
                invite_id=invite["invite_id"],
            )
        except InviteRepositoryError as error:
            raise ValueError("Failed to mark invite as accepted.") from error

        return {
            "status": "ok",
            "org_id": org_id,
            "org_role": org_role_result,
            "team_id": team_id_result,
            "team_role": team_role_result,
        }

    def _validate_org_role_assignment(
        self, *, requester_org_role: Any, requested_org_role: str
    ) -> None:
        if requester_org_role == "OWNER":
            return
        if requester_org_role == "ADMIN" and requested_org_role == "MEMBER":
            return
        raise ForbiddenError("insufficient_org_role")

    def _validate_team_invite_permission(
        self,
        *,
        requester_user_id: str,
        requester_org_role: Any,
        org_id: str,
        team_id: str,
        requested_team_role: str,
    ) -> None:
        if requester_org_role in {"OWNER", "ADMIN"}:
            return

        membership = self._authorization_service.require_team_role(
            user_id=requester_user_id,
            org_id=org_id,
            team_id=team_id,
            allowed_roles={"TEAM_ADMIN"},
        )
        if membership.get("team_role") != "TEAM_ADMIN":
            raise ForbiddenError("insufficient_team_role")
        if requested_team_role == "TEAM_ADMIN":
            raise ForbiddenError("insufficient_team_role")

    @staticmethod
    def _resolve_scope(
        *,
        org_role: Any,
        team_id: Any,
        team_role: Any,
    ) -> str:
        has_org = isinstance(org_role, str) and bool(org_role.strip())
        has_team = (
            isinstance(team_id, str)
            and bool(team_id.strip())
            and isinstance(team_role, str)
            and bool(team_role.strip())
        )
        if has_org and has_team:
            return "org_and_team"
        if has_org:
            return "org"
        if has_team:
            return "team"
        raise ValueError("Invite must include org role or team scope.")

    def _get_user(self, *, user_id: str) -> dict[str, Any]:
        try:
            user = self._user_repository.get_by_user_id(user_id=user_id)
        except UserRepositoryError as error:
            raise InviteNotFoundError("invite_not_found") from error
        if user is None:
            raise InviteNotFoundError("invite_not_found")
        return user


def _parse_iso_datetime(raw_value: Any) -> datetime | None:
    if not isinstance(raw_value, str):
        return None
    normalized = raw_value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

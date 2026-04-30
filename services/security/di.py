from dataclasses import dataclass

from repositories.auth_repository import AuthRepository
from repositories.google_connection_repository import GoogleConnectionRepository
from repositories.google_drive_repository import GoogleDriveRepository
from repositories.helpers.google_oauth_helper import GoogleOAuthHelper
from repositories.invite_repository import InviteRepository
from repositories.organization_repository import OrganizationRepository
from repositories.user_repository import UserRepository
from services.organization_service import OrganizationService
from services.organization_team_service import OrganizationTeamService
from services.security.auth_config import AuthConfig
from services.security.auth_guard import AuthGuard
from services.security.auth_service import AuthService
from services.security.authorization_service import AuthorizationService
from services.security.invite_service import InviteService
from services.security.invite_token_service import InviteTokenService
from services.security.jwt_token_service import JWTTokenService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)
from services.security.state_token_service import StateTokenService
from services.workspace_service import WorkspaceService


@dataclass(frozen=True)
class SecurityContainer:
    auth_config: AuthConfig
    auth_service: AuthService
    auth_guard: AuthGuard
    organization_service: OrganizationService
    organization_team_service: OrganizationTeamService
    invite_service: InviteService


def build_security_container(*, auth_config: AuthConfig | None = None) -> SecurityContainer:
    resolved_auth_config = auth_config or AuthConfig.from_env()

    auth_repository = AuthRepository(google_oauth_helper=GoogleOAuthHelper())
    user_repository = UserRepository()
    google_connection_repository = GoogleConnectionRepository()
    organization_repository = OrganizationRepository()
    invite_repository = InviteRepository()
    google_drive_repository = GoogleDriveRepository()

    token_service = JWTTokenService(auth_config=resolved_auth_config)
    state_token_service = StateTokenService(secret=resolved_auth_config.auth_state_secret)
    refresh_token_encryption_service = RefreshTokenEncryptionService(
        auth_config=resolved_auth_config
    )

    authorization_service = AuthorizationService(
        organization_repository=organization_repository
    )
    invite_token_service = InviteTokenService(
        signing_secret=resolved_auth_config.auth_state_secret
    )
    workspace_service = WorkspaceService(
        auth_config=resolved_auth_config,
        organization_repository=organization_repository,
        google_connection_repository=google_connection_repository,
        google_drive_repository=google_drive_repository,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    organization_service = OrganizationService(
        organization_repository=organization_repository,
        user_repository=user_repository,
        google_connection_repository=google_connection_repository,
        authorization_service=authorization_service,
        workspace_service=workspace_service,
    )
    invite_service = InviteService(
        auth_config=resolved_auth_config,
        invite_repository=invite_repository,
        organization_repository=organization_repository,
        user_repository=user_repository,
        authorization_service=authorization_service,
        invite_token_service=invite_token_service,
    )
    organization_team_service = OrganizationTeamService(
        organization_repository=organization_repository,
        user_repository=user_repository,
        authorization_service=authorization_service,
        invite_service=invite_service,
    )
    auth_service = AuthService(
        auth_config=resolved_auth_config,
        auth_repository=auth_repository,
        user_repository=user_repository,
        google_connection_repository=google_connection_repository,
        organization_repository=organization_repository,
        token_service=token_service,
        state_token_service=state_token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    auth_guard = AuthGuard(auth_service=auth_service)

    return SecurityContainer(
        auth_config=resolved_auth_config,
        auth_service=auth_service,
        auth_guard=auth_guard,
        organization_service=organization_service,
        organization_team_service=organization_team_service,
        invite_service=invite_service,
    )

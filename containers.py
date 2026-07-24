from dependency_injector import containers, providers

from repositories.auth_repository import AuthRepository
from repositories.coach_repository import CoachRepository
from repositories.google_connection_repository import GoogleConnectionRepository
from repositories.google_drive_repository import GoogleDriveRepository
from repositories.helpers.google_oauth_helper import GoogleOAuthHelper
from repositories.invite_repository import InviteRepository
from repositories.monthly_fees_repository import MonthlyFeesRepository
from repositories.organization_repository import OrganizationRepository
from repositories.team_workspace_repository import TeamWorkspaceRepository
from repositories.user_repository import UserRepository
from services.coach_service import CoachService
from services.monthly_fees_service import MonthlyFeesService
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


class ApplicationContainer(containers.DeclarativeContainer):
    google_oauth_helper = providers.Singleton(GoogleOAuthHelper)
    google_drive_repository = providers.Singleton(GoogleDriveRepository)
    team_workspace_repository = providers.Singleton(TeamWorkspaceRepository)
    coach_repository = providers.Singleton(CoachRepository)
    monthly_fees_repository = providers.Singleton(MonthlyFeesRepository)

    auth_repository = providers.Singleton(
        AuthRepository,
        google_oauth_helper=google_oauth_helper,
    )
    user_repository = providers.Singleton(UserRepository)
    google_connection_repository = providers.Singleton(GoogleConnectionRepository)
    organization_repository = providers.Singleton(OrganizationRepository)
    invite_repository = providers.Singleton(InviteRepository)

    auth_config = providers.Singleton(AuthConfig.from_env)
    token_service = providers.Singleton(JWTTokenService, auth_config=auth_config)
    state_token_service = providers.Singleton(
        StateTokenService,
        secret=auth_config.provided.auth_state_secret,
    )
    refresh_token_encryption_service = providers.Singleton(
        RefreshTokenEncryptionService,
        auth_config=auth_config,
    )
    invite_token_service = providers.Singleton(
        InviteTokenService,
        signing_secret=auth_config.provided.auth_state_secret,
    )
    authorization_service = providers.Singleton(
        AuthorizationService,
        organization_repository=organization_repository,
    )
    workspace_service = providers.Singleton(
        WorkspaceService,
        auth_config=auth_config,
        organization_repository=organization_repository,
        google_connection_repository=google_connection_repository,
        google_drive_repository=google_drive_repository,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    organization_service = providers.Singleton(
        OrganizationService,
        organization_repository=organization_repository,
        user_repository=user_repository,
        google_connection_repository=google_connection_repository,
        authorization_service=authorization_service,
        workspace_service=workspace_service,
    )
    invite_service = providers.Singleton(
        InviteService,
        auth_config=auth_config,
        invite_repository=invite_repository,
        organization_repository=organization_repository,
        user_repository=user_repository,
        authorization_service=authorization_service,
        invite_token_service=invite_token_service,
    )
    organization_team_service = providers.Singleton(
        OrganizationTeamService,
        auth_config=auth_config,
        organization_repository=organization_repository,
        user_repository=user_repository,
        google_connection_repository=google_connection_repository,
        team_workspace_repository=team_workspace_repository,
        refresh_token_encryption_service=refresh_token_encryption_service,
        workspace_service=workspace_service,
        authorization_service=authorization_service,
        invite_service=invite_service,
    )
    coach_service = providers.Singleton(
        CoachService,
        auth_config=auth_config,
        organization_repository=organization_repository,
        google_connection_repository=google_connection_repository,
        coach_repository=coach_repository,
        refresh_token_encryption_service=refresh_token_encryption_service,
        authorization_service=authorization_service,
        workspace_service=workspace_service,
    )
    monthly_fees_service = providers.Singleton(
        MonthlyFeesService,
        auth_config=auth_config,
        organization_repository=organization_repository,
        google_connection_repository=google_connection_repository,
        refresh_token_encryption_service=refresh_token_encryption_service,
        authorization_service=authorization_service,
        monthly_fees_repository=monthly_fees_repository,
    )
    auth_service = providers.Singleton(
        AuthService,
        auth_config=auth_config,
        auth_repository=auth_repository,
        user_repository=user_repository,
        google_connection_repository=google_connection_repository,
        organization_repository=organization_repository,
        token_service=token_service,
        state_token_service=state_token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    auth_guard = providers.Singleton(AuthGuard, auth_service=auth_service)

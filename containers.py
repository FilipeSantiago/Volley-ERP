import os

from dependency_injector import containers, providers

from repositories.athlete_repository import AthleteRepository
from repositories.auth_repository import AuthRepository
from repositories.customer_repository import CustomerRepository
from repositories.helpers.google_drive_folders_helper import GoogleDriveFoldersHelper
from repositories.helpers.google_oauth_helper import GoogleOAuthHelper
from repositories.helpers.google_sheets_helper import GoogleSheetsHelper
from repositories.helpers.google_workspace_helper import GoogleWorkspaceHelper
from repositories.team_repository import TeamRepository
from repositories.workspace_repository import WorkspaceRepository
from services.athlete_service import AthleteService
from services.security.auth_config import AuthConfig
from services.security.auth_guard import AuthGuard
from services.security.auth_service import AuthService
from services.security.customer_service import CustomerService
from services.security.jwt_token_service import JWTTokenService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)
from services.security.state_token_service import StateTokenService
from services.team_service import TeamService


class ApplicationContainer(containers.DeclarativeContainer):
    customer_root_folder_id = providers.Object(os.getenv("CUSTOMER_ROOT_FOLDER_ID"))

    drive_folders_helper = providers.Singleton(GoogleDriveFoldersHelper)
    sheets_helper = providers.Singleton(GoogleSheetsHelper)
    google_oauth_helper = providers.Singleton(GoogleOAuthHelper)
    google_workspace_helper = providers.Singleton(GoogleWorkspaceHelper)

    team_repository = providers.Singleton(
        TeamRepository,
        drive_folders_helper=drive_folders_helper,
    )
    athlete_repository = providers.Singleton(
        AthleteRepository,
        drive_folders_helper=drive_folders_helper,
        sheets_helper=sheets_helper,
    )
    auth_repository = providers.Singleton(
        AuthRepository,
        google_oauth_helper=google_oauth_helper,
    )
    customer_repository = providers.Singleton(CustomerRepository)
    workspace_repository = providers.Singleton(
        WorkspaceRepository,
        workspace_helper=google_workspace_helper,
    )

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

    team_service = providers.Singleton(
        TeamService,
        team_repository=team_repository,
        root_folder_id=customer_root_folder_id,
    )
    athlete_service = providers.Singleton(
        AthleteService,
        athlete_repository=athlete_repository,
    )
    auth_service = providers.Singleton(
        AuthService,
        auth_config=auth_config,
        auth_repository=auth_repository,
        customer_repository=customer_repository,
        token_service=token_service,
        state_token_service=state_token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    customer_service = providers.Singleton(
        CustomerService,
        auth_config=auth_config,
        customer_repository=customer_repository,
        workspace_repository=workspace_repository,
        token_service=token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    auth_guard = providers.Singleton(AuthGuard, auth_service=auth_service)

from dataclasses import dataclass

from repositories.auth_repository import AuthRepository
from repositories.customer_repository import CustomerRepository
from repositories.helpers.google_oauth_helper import GoogleOAuthHelper
from repositories.helpers.google_workspace_helper import GoogleWorkspaceHelper
from repositories.workspace_repository import WorkspaceRepository
from services.security.auth_config import AuthConfig
from services.security.auth_guard import AuthGuard
from services.security.auth_service import AuthService
from services.security.customer_service import CustomerService
from services.security.jwt_token_service import JWTTokenService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)
from services.security.state_token_service import StateTokenService


@dataclass(frozen=True)
class SecurityContainer:
    auth_config: AuthConfig
    auth_service: AuthService
    auth_guard: AuthGuard
    customer_service: CustomerService


def build_security_container(*, auth_config: AuthConfig | None = None) -> SecurityContainer:
    resolved_auth_config = auth_config or AuthConfig.from_env()

    auth_repository = AuthRepository(google_oauth_helper=GoogleOAuthHelper())
    customer_repository = CustomerRepository()
    workspace_repository = WorkspaceRepository(workspace_helper=GoogleWorkspaceHelper())

    token_service = JWTTokenService(auth_config=resolved_auth_config)
    state_token_service = StateTokenService(secret=resolved_auth_config.auth_state_secret)
    refresh_token_encryption_service = RefreshTokenEncryptionService(
        auth_config=resolved_auth_config
    )

    auth_service = AuthService(
        auth_config=resolved_auth_config,
        auth_repository=auth_repository,
        customer_repository=customer_repository,
        token_service=token_service,
        state_token_service=state_token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    customer_service = CustomerService(
        auth_config=resolved_auth_config,
        customer_repository=customer_repository,
        workspace_repository=workspace_repository,
        token_service=token_service,
        refresh_token_encryption_service=refresh_token_encryption_service,
    )
    auth_guard = AuthGuard(auth_service=auth_service)

    return SecurityContainer(
        auth_config=resolved_auth_config,
        auth_service=auth_service,
        auth_guard=auth_guard,
        customer_service=customer_service,
    )

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from services.security.auth_exceptions import (
    DisallowedPlatformClientMismatchError,
    ForbiddenError,
    InvalidCodeError,
    InvalidCodeVerifierError,
    InvalidRedirectURIError,
    InvalidStateError,
    InvalidTokenError,
    InviteAlreadyAcceptedError,
    InviteEmailMismatchError,
    InviteExpiredError,
    InviteNotFoundError,
    OAuthConfigurationError,
    OAuthProviderError,
    OrganizationNotFoundError,
    StorageOwnerConnectionMissingError,
    TeamNotFoundError,
    TokenExpiredError,
    UnauthorizedError,
    WorkspaceProvisioningFailedError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def handle_value_error(_, error: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "message": str(error)},
        )

    @app.exception_handler(InvalidRedirectURIError)
    async def handle_invalid_redirect_uri(_, error: InvalidRedirectURIError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_redirect_uri", "message": str(error)},
        )

    @app.exception_handler(InvalidStateError)
    async def handle_invalid_state(_, error: InvalidStateError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_state", "message": str(error)},
        )

    @app.exception_handler(InvalidCodeVerifierError)
    async def handle_invalid_code_verifier(_, error: InvalidCodeVerifierError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_code_verifier", "message": str(error)},
        )

    @app.exception_handler(InvalidCodeError)
    async def handle_invalid_code(_, error: InvalidCodeError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_code", "message": str(error)},
        )

    @app.exception_handler(DisallowedPlatformClientMismatchError)
    async def handle_disallowed_platform_client_mismatch(
        _, error: DisallowedPlatformClientMismatchError
    ):
        return JSONResponse(
            status_code=400,
            content={
                "error": "disallowed_platform_client_mismatch",
                "message": str(error),
            },
        )

    @app.exception_handler(OAuthProviderError)
    async def handle_oauth_provider_error(_, error: OAuthProviderError):
        content = {"error": error.error}
        if error.error_description:
            content["error_description"] = error.error_description
        return JSONResponse(status_code=400, content=content)

    @app.exception_handler(OAuthConfigurationError)
    async def handle_oauth_configuration_error(_, error: OAuthConfigurationError):
        return JSONResponse(
            status_code=500,
            content={"error": "oauth_not_configured", "message": str(error)},
        )

    @app.exception_handler(TokenExpiredError)
    async def handle_token_expired(_, __: TokenExpiredError):
        return JSONResponse(
            status_code=401,
            content={"error": "token_expired"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(InvalidTokenError)
    async def handle_invalid_token(_, __: InvalidTokenError):
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(UnauthorizedError)
    async def handle_unauthorized(_, __: UnauthorizedError):
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ForbiddenError)
    async def handle_forbidden(_, error: ForbiddenError):
        return JSONResponse(
            status_code=403,
            content={"error": "forbidden", "reason": error.reason},
        )

    @app.exception_handler(OrganizationNotFoundError)
    async def handle_org_not_found(_, __: OrganizationNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "organization_not_found"},
        )

    @app.exception_handler(TeamNotFoundError)
    async def handle_team_not_found(_, __: TeamNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "team_not_found"},
        )

    @app.exception_handler(InviteNotFoundError)
    async def handle_invite_not_found(_, __: InviteNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "invite_not_found"},
        )

    @app.exception_handler(InviteExpiredError)
    async def handle_invite_expired(_, __: InviteExpiredError):
        return JSONResponse(
            status_code=400,
            content={"error": "invite_expired"},
        )

    @app.exception_handler(InviteAlreadyAcceptedError)
    async def handle_invite_already_accepted(_, __: InviteAlreadyAcceptedError):
        return JSONResponse(
            status_code=400,
            content={"error": "invite_already_accepted"},
        )

    @app.exception_handler(InviteEmailMismatchError)
    async def handle_invite_email_mismatch(_, __: InviteEmailMismatchError):
        return JSONResponse(
            status_code=403,
            content={"error": "invite_email_mismatch"},
        )

    @app.exception_handler(StorageOwnerConnectionMissingError)
    async def handle_storage_owner_connection_missing(
        _, __: StorageOwnerConnectionMissingError
    ):
        return JSONResponse(
            status_code=409,
            content={"error": "storage_owner_connection_missing"},
        )

    @app.exception_handler(WorkspaceProvisioningFailedError)
    async def handle_workspace_provisioning_failed(
        _, __: WorkspaceProvisioningFailedError
    ):
        return JSONResponse(
            status_code=500,
            content={"error": "workspace_provisioning_failed"},
        )

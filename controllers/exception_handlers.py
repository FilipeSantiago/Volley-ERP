from fastapi import FastAPI
from fastapi.responses import JSONResponse

from services.exceptions import (
    AthleteCreationError,
    InvalidAthletePayloadError,
    InvalidTeamNameError,
    RootFolderNotConfiguredError,
    TeamAlreadyExistsError,
    TeamCreationError,
    TeamFolderNotFoundError,
)
from services.security.auth_exceptions import (
    CustomerNotFoundError,
    DisallowedPlatformClientMismatchError,
    InvalidCodeError,
    InvalidCodeVerifierError,
    InvalidRedirectURIError,
    InvalidStateError,
    InvalidTokenError,
    OAuthConfigurationError,
    OAuthProviderError,
    TokenExpiredError,
    UnauthorizedError,
    WorkspaceCreationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(InvalidTeamNameError)
    async def handle_invalid_team_name(_, error: InvalidTeamNameError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_team_name", "message": str(error)},
        )

    @app.exception_handler(RootFolderNotConfiguredError)
    async def handle_root_folder_not_configured(_, error: RootFolderNotConfiguredError):
        return JSONResponse(
            status_code=500,
            content={"error": "root_folder_not_configured", "message": str(error)},
        )

    @app.exception_handler(TeamAlreadyExistsError)
    async def handle_team_already_exists(_, error: TeamAlreadyExistsError):
        return JSONResponse(
            status_code=409,
            content={
                "error": "team_already_exists",
                "message": str(error),
                "team_folder_id": error.team_folder_id,
            },
        )

    @app.exception_handler(TeamCreationError)
    async def handle_team_creation_error(_, error: TeamCreationError):
        return JSONResponse(
            status_code=502,
            content={"error": "team_creation_failed", "message": str(error)},
        )

    @app.exception_handler(InvalidAthletePayloadError)
    async def handle_invalid_athlete_payload(_, error: InvalidAthletePayloadError):
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_athlete_payload", "message": str(error)},
        )

    @app.exception_handler(TeamFolderNotFoundError)
    async def handle_team_folder_not_found(_, error: TeamFolderNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "team_folder_not_found", "message": str(error)},
        )

    @app.exception_handler(AthleteCreationError)
    async def handle_athlete_creation_error(_, error: AthleteCreationError):
        return JSONResponse(
            status_code=502,
            content={"error": "athlete_creation_failed", "message": str(error)},
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

    @app.exception_handler(CustomerNotFoundError)
    async def handle_customer_not_found(_, error: CustomerNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "customer_not_found", "message": str(error)},
        )

    @app.exception_handler(WorkspaceCreationError)
    async def handle_workspace_creation_error(_, error: WorkspaceCreationError):
        return JSONResponse(
            status_code=502,
            content={"error": "workspace_creation_failed", "message": str(error)},
        )

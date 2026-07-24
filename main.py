from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from containers import ApplicationContainer
from controllers.athletes_controller import create_athletes_router
from controllers.auth_controller import create_auth_router
from controllers.coach_controller import create_coach_router
from controllers.exception_handlers import register_exception_handlers
from controllers.monthly_fees_controller import create_monthly_fees_router
from controllers.organization_controller import create_organizations_router
from controllers.team_controller import create_teams_router


def _load_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS")
    if not raw or not raw.strip():
        return ["*"]

    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or ["*"]


def _load_cors_allow_credentials(origins: list[str]) -> bool:
    raw = os.getenv("CORS_ALLOW_CREDENTIALS", "true").strip().lower()
    requested = raw in {"1", "true", "yes", "on"}
    if requested and "*" in origins:
        return False
    return requested


load_dotenv()

container = ApplicationContainer()
cors_origins = _load_cors_origins()
app = FastAPI(title="Volley ERP API")
app.state.container = container

register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=_load_cors_allow_credentials(cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    create_auth_router(container.auth_service(), container.auth_guard())
)
app.include_router(
    create_organizations_router(
        container.organization_service(),
        container.invite_service(),
        container.auth_guard(),
    )
)
app.include_router(
    create_teams_router(
        container.organization_team_service(),
        container.auth_guard(),
    )
)
app.include_router(
    create_athletes_router(
        container.organization_team_service(),
        container.auth_guard(),
    )
)
app.include_router(
    create_coach_router(
        container.coach_service(),
        container.auth_guard(),
    )
)
app.include_router(
    create_monthly_fees_router(
        container.monthly_fees_service(),
        container.auth_guard(),
    )
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Volley ERP FastAPI service.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface for uvicorn.")
    parser.add_argument("--port", type=int, default=8000, help="Port for uvicorn.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload.")
    args = parser.parse_args()

    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()

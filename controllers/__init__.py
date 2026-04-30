from controllers.athletes_controller import create_athletes_router
from controllers.auth_controller import create_auth_router
from controllers.organization_controller import create_organizations_router
from controllers.team_controller import create_teams_router

__all__ = [
    "create_athletes_router",
    "create_auth_router",
    "create_organizations_router",
    "create_teams_router",
]

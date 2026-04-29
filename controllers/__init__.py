from controllers.auth_controller import create_auth_router
from controllers.athlete_controller import create_athletes_router
from controllers.customer_controller import create_customer_router
from controllers.team_controller import create_teams_router

__all__ = [
    "create_athletes_router",
    "create_auth_router",
    "create_customer_router",
    "create_teams_router",
]

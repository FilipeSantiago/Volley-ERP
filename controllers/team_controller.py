from typing import Annotated, Any

from fastapi import APIRouter, Depends

from controllers.security_dependencies import create_access_claims_dependency
from models.team import (
    CreateTeamRequest,
    Team,
    TeamDetailQuery,
    TeamListResponse,
    TeamMemberCreateRequest,
    TeamMemberMutationResponse,
    TeamMembersResponse,
    TeamQuery,
)
from services.organization_team_service import OrganizationTeamService
from services.security.auth_guard import AuthGuard


def create_teams_router(
    organization_team_service: OrganizationTeamService,
    auth_guard: AuthGuard,
) -> APIRouter:
    router = APIRouter()
    access_claims_dependency = create_access_claims_dependency(auth_guard=auth_guard)

    @router.post("/teams", response_model=Team, status_code=201)
    def create_team(
        body: CreateTeamRequest,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_team_service.create_team(
            user_id=user_id,
            org_id=body.org_id,
            payload={
                "name": body.name,
                "category": body.category,
                "gender": body.gender,
            },
        )
        return result

    @router.get("/teams", response_model=TeamListResponse, status_code=200)
    def list_teams(
        query: Annotated[TeamQuery, Depends()],
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_team_service.list_teams(
            user_id=user_id,
            org_id=query.org_id,
        )
        return result

    @router.get("/teams/detail", response_model=Team, status_code=200)
    def get_team(
        query: Annotated[TeamDetailQuery, Depends()],
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_team_service.get_team(
            user_id=user_id,
            org_id=query.org_id,
            team_id=query.team_id,
        )
        return result

    @router.post("/teams/members", response_model=TeamMemberMutationResponse, status_code=200)
    def add_team_member(
        body: TeamMemberCreateRequest,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_team_service.add_team_member(
            user_id=user_id,
            org_id=body.org_id,
            team_id=body.team_id,
            payload={
                "email": body.email,
                "team_role": body.team_role,
            },
        )
        return result

    @router.get("/teams/members", response_model=TeamMembersResponse, status_code=200)
    def list_team_members(
        query: Annotated[TeamDetailQuery, Depends()],
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_team_service.list_team_members(
            user_id=user_id,
            org_id=query.org_id,
            team_id=query.team_id,
        )
        return result

    return router

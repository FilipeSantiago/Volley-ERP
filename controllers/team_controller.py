import json
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from services.team_service import TeamService


def create_teams_router(team_service: TeamService) -> APIRouter:
    teams_router = APIRouter()

    @teams_router.get("/teams")
    def list_teams():
        result = team_service.list_teams()
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result,
        )

    @teams_router.post("/teams")
    async def create_team(request: Request):
        payload = await _parse_json_payload(request)
        if payload is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "invalid_json",
                    "message": "Request body must be valid JSON.",
                },
            )

        team_name = payload.get("team_name")
        result = team_service.create_team(team_name)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=result,
        )

    return teams_router


async def _parse_json_payload(request: Request) -> dict[str, Any] | None:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload

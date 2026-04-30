import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from controllers.security_dependencies import create_access_claims_dependency
from services.security.auth_guard import AuthGuard
from services.security.auth_service import AuthService


def create_auth_router(auth_service: AuthService, auth_guard: AuthGuard) -> APIRouter:
    auth_router = APIRouter()
    access_claims_dependency = create_access_claims_dependency(auth_guard=auth_guard)

    @auth_router.get("/auth/google/start")
    def auth_google_start(
        redirect_uri: str | None = Query(default=None),
        platform: str | None = Query(default=None),
    ):
        result = auth_service.start_google_auth(
            redirect_uri=redirect_uri,
            platform=platform,
        )

        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    @auth_router.get("/auth/google/callback")
    def auth_google_callback(request: Request):
        result = auth_service.handle_google_callback(
            params=dict(request.query_params)
        )

        if result.get("mode") == "redirect":
            return RedirectResponse(
                url=result["redirect_url"],
                status_code=status.HTTP_302_FOUND,
            )

        return JSONResponse(
            status_code=result.get("status_code", status.HTTP_200_OK),
            content=result["payload"],
        )

    @auth_router.post("/auth/google/mobile")
    async def auth_google_mobile(request: Request):
        payload = await _parse_json_payload(request)
        if payload is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "invalid_json",
                    "message": "Request body must be valid JSON.",
                },
            )

        result = auth_service.exchange_google_mobile_code(payload=payload)

        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    @auth_router.post("/security/refresh")
    async def security_refresh(request: Request):
        payload = await _parse_json_payload(request)
        if payload is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "invalid_json",
                    "message": "Request body must be valid JSON.",
                },
            )

        refresh_token = payload.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "invalid_request",
                    "message": "refresh_token is required.",
                },
            )

        token_pair = auth_service.refresh_token_pair(refresh_token=refresh_token)

        return JSONResponse(status_code=status.HTTP_200_OK, content=token_pair)

    @auth_router.get("/security/me")
    def security_me(
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        me = auth_service.get_me_from_claims(claims=claims)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=me,
        )

    return auth_router

async def _parse_json_payload(request: Request) -> dict[str, Any] | None:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload

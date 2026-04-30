import json
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from controllers.security_dependencies import create_access_claims_dependency
from models.organization import (
    CreateOrganizationRequest,
    CreateOrganizationResponse,
    Organization,
    OrganizationListResponse,
)
from services.organization_service import OrganizationService
from services.security.auth_guard import AuthGuard
from services.security.invite_service import InviteService


def create_organizations_router(
    organization_service: OrganizationService,
    invite_service: InviteService,
    auth_guard: AuthGuard,
) -> APIRouter:
    router = APIRouter()
    access_claims_dependency = create_access_claims_dependency(auth_guard=auth_guard)

    @router.post(
        "/organizations",
        response_model=CreateOrganizationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_organization(
        body: CreateOrganizationRequest,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_service.create_organization(
            user_id=user_id,
            payload=body.model_dump(),
        )
        return result

    @router.get(
        "/organizations",
        response_model=OrganizationListResponse,
        status_code=status.HTTP_200_OK,
    )
    def list_organizations(claims: dict[str, Any] = Depends(access_claims_dependency)):
        user_id = claims.get("sub")
        items = organization_service.list_organizations(user_id=user_id)
        return {"items": items, "count": len(items)}

    @router.get(
        "/organizations/{org_id}",
        response_model=Organization,
        status_code=status.HTTP_200_OK,
    )
    def get_organization(org_id: str, claims: dict[str, Any] = Depends(access_claims_dependency)):
        user_id = claims.get("sub")
        result = organization_service.get_organization(user_id=user_id, org_id=org_id)
        return result

    @router.post("/organizations/{org_id}/workspace/ensure")
    def ensure_workspace(org_id: str, claims: dict[str, Any] = Depends(access_claims_dependency)):
        user_id = claims.get("sub")
        result = organization_service.ensure_workspace(user_id=user_id, org_id=org_id)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    @router.post("/organizations/{org_id}/invites")
    async def create_invite(
        org_id: str,
        request: Request,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        payload = await _parse_json_payload(request)
        if payload is None:
            return _invalid_json_response()

        user_id = claims.get("sub")
        result = invite_service.create_invite(
            user_id=user_id,
            org_id=org_id,
            payload=payload,
        )
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=result)

    @router.post("/organizations/invites/accept")
    async def accept_invite(
        request: Request,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        payload = await _parse_json_payload(request)
        if payload is None:
            return _invalid_json_response()

        token = payload.get("token")
        if not isinstance(token, str) or not token.strip():
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"error": "invalid_request", "message": "token is required."},
            )

        user_id = claims.get("sub")
        result = invite_service.accept_invite(user_id=user_id, token=token)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    @router.get("/organizations/{org_id}/members")
    def list_org_members(
        org_id: str,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_service.list_members(user_id=user_id, org_id=org_id)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    @router.delete("/organizations/{org_id}/members/{user_id}")
    def remove_org_member(
        org_id: str,
        user_id: str,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        requester_user_id = claims.get("sub")
        result = organization_service.remove_member(
            requester_user_id=requester_user_id,
            org_id=org_id,
            target_user_id=user_id,
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    return router


def _invalid_json_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "invalid_json",
            "message": "Request body must be valid JSON.",
        },
    )


async def _parse_json_payload(request: Request) -> dict[str, Any] | None:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload

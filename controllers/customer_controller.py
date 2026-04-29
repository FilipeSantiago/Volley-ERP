import json
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from controllers.security_dependencies import create_access_claims_dependency
from services.security.auth_guard import AuthGuard
from services.security.customer_service import CustomerService


def create_customer_router(
    customer_service: CustomerService, auth_guard: AuthGuard
) -> APIRouter:
    customer_router = APIRouter()
    access_claims_dependency = create_access_claims_dependency(auth_guard=auth_guard)

    @customer_router.post("/customer/workspace")
    async def create_workspace(
        request: Request,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        payload = await _parse_json_payload(request) or {}
        workspace_name = payload.get("workspace_name")
        customer_id = claims.get("sub")

        result = customer_service.create_workspace(
            customer_id=customer_id,
            workspace_name=workspace_name,
        )

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=result)

    return customer_router


async def _parse_json_payload(request: Request) -> dict[str, Any] | None:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    return payload

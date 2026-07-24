from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from controllers.security_dependencies import create_access_claims_dependency
from models.monthly_fee import (
    MonthlyFeeCreateRequest,
    MonthlyFeeEntry,
    MonthlyFeeListQuery,
    MonthlyFeeListResponse,
    MonthlyFeeUpdateRequest,
)
from services.monthly_fees_service import MonthlyFeesService
from services.security.auth_guard import AuthGuard


def create_monthly_fees_router(
    monthly_fees_service: MonthlyFeesService,
    auth_guard: AuthGuard,
) -> APIRouter:
    _validate_monthly_fees_service_contract(monthly_fees_service)
    router = APIRouter()
    access_claims_dependency = create_access_claims_dependency(auth_guard=auth_guard)

    @router.get("/monthly_fees", response_model=MonthlyFeeListResponse, status_code=200)
    def list_monthly_fees(
        query: Annotated[MonthlyFeeListQuery, Depends()],
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = monthly_fees_service.list_monthly_fees(
            user_id=user_id,
            team_id=query.team_id,
            tag=query.tag.value if query.tag else None,
            athlete_id=query.athlete_id,
            include_inactive=query.include_inactive,
        )
        return result

    @router.post("/monthly_fees", response_model=MonthlyFeeEntry, status_code=201)
    def create_monthly_fee(
        body: MonthlyFeeCreateRequest,
        team_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        resolved_team_id = _resolve_team_id(
            body_team_id=body.team_id,
            query_team_id=team_id,
        )
        result = monthly_fees_service.create_monthly_fee(
            user_id=user_id,
            team_id=resolved_team_id,
            tag=body.tag.value,
            amount=body.amount,
            currency=body.currency,
            athlete_id=body.athlete_id,
            person_name=body.person_name,
            description=body.description,
        )
        return result

    @router.put("/monthly_fees/{fee_id}", response_model=MonthlyFeeEntry, status_code=200)
    def update_monthly_fee(
        fee_id: str,
        body: MonthlyFeeUpdateRequest,
        team_id: str | None = Query(default=None),
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        resolved_team_id = _resolve_team_id(
            body_team_id=body.team_id,
            query_team_id=team_id,
        )
        result = monthly_fees_service.update_monthly_fee(
            user_id=user_id,
            team_id=resolved_team_id,
            fee_id=fee_id,
            amount=body.amount,
            currency=body.currency,
            description=body.description,
        )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "monthly_fee_not_found"},
            )
        return result

    @router.delete("/monthly_fees/{fee_id}", response_model=MonthlyFeeEntry, status_code=200)
    def deactivate_monthly_fee(
        fee_id: str,
        team_id: str = Query(min_length=1),
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = monthly_fees_service.soft_delete_monthly_fee(
            user_id=user_id,
            team_id=team_id,
            fee_id=fee_id,
        )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "monthly_fee_not_found"},
            )
        return result

    return router


def _resolve_team_id(*, body_team_id: str | None, query_team_id: str | None) -> str:
    normalized_body = body_team_id.strip() if isinstance(body_team_id, str) else ""
    normalized_query = query_team_id.strip() if isinstance(query_team_id, str) else ""
    if normalized_body and normalized_query and normalized_body != normalized_query:
        raise ValueError("team_id mismatch between body and query params.")
    team_id = normalized_body or normalized_query
    if not team_id:
        raise ValueError("team_id is required.")
    return team_id


def _validate_monthly_fees_service_contract(monthly_fees_service: Any) -> None:
    required_methods = (
        "list_monthly_fees",
        "create_monthly_fee",
        "update_monthly_fee",
        "soft_delete_monthly_fee",
    )
    missing = [
        method_name
        for method_name in required_methods
        if not callable(getattr(monthly_fees_service, method_name, None))
    ]
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(
            "MonthlyFeesService/router version mismatch. "
            f"Missing method(s): {missing_str}. Restart the API process with matching code."
        )

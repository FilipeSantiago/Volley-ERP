from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import JSONResponse

from controllers.security_dependencies import create_access_claims_dependency
from models.coach import (
    CoachCreateRequest,
    CoachQuery,
    CoachResponse,
    CoachUpdateRequest,
)
from services.coach_service import CoachService
from services.security.auth_guard import AuthGuard


def coach_create_form_dependency(
    org_id: str = Form(...),
    team_id: str = Form(...),
    full_name: str = Form(...),
    birthday: str = Form(...),
    cpf: str = Form(...),
    cellphone: str = Form(...),
    position: str = Form(...),
    pix_key: str = Form(...),
    tshirt_size: str | None = Form(default=None),
    shorts_size: str | None = Form(default=None),
    rg: str | None = Form(default=None),
    email: str | None = Form(default=None),
) -> CoachCreateRequest:
    return CoachCreateRequest(
        org_id=org_id,
        team_id=team_id,
        full_name=full_name,
        birthday=birthday,
        cpf=cpf,
        cellphone=cellphone,
        position=position,
        pix_key=pix_key,
        tshirt_size=tshirt_size,
        shorts_size=shorts_size,
        rg=rg,
        email=email,
    )


def coach_update_form_dependency(
    org_id: str = Form(...),
    team_id: str = Form(...),
    full_name: str = Form(...),
    birthday: str = Form(...),
    cpf: str = Form(...),
    cellphone: str = Form(...),
    position: str = Form(...),
    pix_key: str = Form(...),
    tshirt_size: str | None = Form(default=None),
    shorts_size: str | None = Form(default=None),
    rg: str | None = Form(default=None),
    email: str | None = Form(default=None),
) -> CoachUpdateRequest:
    return CoachUpdateRequest(
        org_id=org_id,
        team_id=team_id,
        full_name=full_name,
        birthday=birthday,
        cpf=cpf,
        cellphone=cellphone,
        position=position,
        pix_key=pix_key,
        tshirt_size=tshirt_size,
        shorts_size=shorts_size,
        rg=rg,
        email=email,
    )


def create_coach_router(
    coach_service: CoachService,
    auth_guard: AuthGuard,
) -> APIRouter:
    router = APIRouter()
    access_claims_dependency = create_access_claims_dependency(auth_guard=auth_guard)

    @router.post("/coach", response_model=CoachResponse, status_code=201)
    async def create_coach(
        body: Annotated[CoachCreateRequest, Depends(coach_create_form_dependency)],
        photo: UploadFile | None = File(default=None),
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        if photo is None:
            return JSONResponse(
                status_code=400,
                content={"error": "missing_photo", "message": "photo is required."},
            )
        user_id = claims.get("sub")
        result = coach_service.create_coach(
            user_id=user_id,
            org_id=body.org_id,
            team_id=body.team_id,
            payload={
                **_build_coach_payload(body=body),
                "photo_filename": photo.filename,
                "photo_mime_type": photo.content_type,
                "photo_content": await photo.read(),
            },
        )
        return result

    @router.put("/coach", response_model=CoachResponse, status_code=200)
    async def update_coach(
        body: Annotated[CoachUpdateRequest, Depends(coach_update_form_dependency)],
        photo: UploadFile | None = File(default=None),
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        payload: dict[str, Any] = _build_coach_payload(body=body)
        if photo is not None:
            payload.update(
                {
                    "photo_filename": photo.filename,
                    "photo_mime_type": photo.content_type,
                    "photo_content": await photo.read(),
                }
            )

        result = coach_service.update_coach(
            user_id=user_id,
            org_id=body.org_id,
            team_id=body.team_id,
            payload=payload,
        )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "coach_not_found"},
            )
        return result

    @router.get("/coach", response_model=CoachResponse, status_code=200)
    def get_coach(
        query: Annotated[CoachQuery, Depends()],
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = coach_service.get_coach(
            user_id=user_id,
            org_id=query.org_id,
            team_id=query.team_id,
        )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "coach_not_found"},
            )
        return result

    @router.get("/coach/photo", status_code=200)
    def get_coach_photo(
        query: Annotated[CoachQuery, Depends()],
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = coach_service.get_coach_photo(
            user_id=user_id,
            org_id=query.org_id,
            team_id=query.team_id,
        )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "coach_not_found"},
            )
        content = result.get("content")
        if not isinstance(content, bytes):
            return JSONResponse(
                status_code=404,
                content={"error": "coach_not_found"},
            )
        file_name = result.get("file_name")
        if not isinstance(file_name, str) or not file_name.strip():
            file_name = f"{query.team_id}.jpg"
        media_type = result.get("mime_type")
        if not isinstance(media_type, str) or not media_type.strip():
            media_type = "application/octet-stream"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{file_name}"'},
        )

    return router


def _build_coach_payload(
    *,
    body: CoachCreateRequest | CoachUpdateRequest,
) -> dict[str, Any]:
    return {
        "full_name": body.full_name,
        "birthday": body.birthday,
        "cpf": body.cpf,
        "cellphone": body.cellphone,
        "position": body.position.value,
        "pix_key": body.pix_key,
        "tshirt_size": body.tshirt_size.value if body.tshirt_size else None,
        "shorts_size": body.shorts_size.value if body.shorts_size else None,
        "rg": body.rg,
        "email": body.email,
    }

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import JSONResponse

from controllers.security_dependencies import create_access_claims_dependency
from models.athlete import (
    AthleteCreateRequest,
    AthleteListQuery,
    AthleteListResponse,
    AthleteUpdateRequest,
    AthleteWriteResponse,
)
from services.organization_team_service import OrganizationTeamService
from services.security.auth_guard import AuthGuard


def athlete_create_form_dependency(
    org_id: str = Form(...),
    team_id: str = Form(...),
    full_name: str = Form(...),
    birthday: str = Form(...),
    cpf: str = Form(...),
    cellphone: str = Form(...),
    position: str = Form(...),
    tshirt_size: str | None = Form(default=None),
    shorts_size: str | None = Form(default=None),
    rg: str | None = Form(default=None),
    email: str | None = Form(default=None),
) -> AthleteCreateRequest:
    return AthleteCreateRequest(
        org_id=org_id,
        team_id=team_id,
        full_name=full_name,
        birthday=birthday,
        cpf=cpf,
        cellphone=cellphone,
        position=position,
        tshirt_size=tshirt_size,
        shorts_size=shorts_size,
        rg=rg,
        email=email,
    )


def athlete_update_form_dependency(
    org_id: str = Form(...),
    team_id: str = Form(...),
    athlete_id: str = Form(...),
    full_name: str = Form(...),
    birthday: str = Form(...),
    cpf: str = Form(...),
    cellphone: str = Form(...),
    position: str = Form(...),
    tshirt_size: str | None = Form(default=None),
    shorts_size: str | None = Form(default=None),
    rg: str | None = Form(default=None),
    email: str | None = Form(default=None),
) -> AthleteUpdateRequest:
    return AthleteUpdateRequest(
        org_id=org_id,
        team_id=team_id,
        athlete_id=athlete_id,
        full_name=full_name,
        birthday=birthday,
        cpf=cpf,
        cellphone=cellphone,
        position=position,
        tshirt_size=tshirt_size,
        shorts_size=shorts_size,
        rg=rg,
        email=email,
    )


def create_athletes_router(
    organization_team_service: OrganizationTeamService,
    auth_guard: AuthGuard,
) -> APIRouter:
    router = APIRouter()
    access_claims_dependency = create_access_claims_dependency(auth_guard=auth_guard)

    @router.post("/athletes", response_model=AthleteWriteResponse, status_code=201)
    async def create_athlete(
        body: Annotated[AthleteCreateRequest, Depends(athlete_create_form_dependency)],
        photo: UploadFile | None = File(default=None),
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        if photo is None:
            return JSONResponse(
                status_code=400,
                content={"error": "missing_photo", "message": "photo is required."},
            )

        user_id = claims.get("sub")
        result = organization_team_service.create_athlete(
            user_id=user_id,
            org_id=body.org_id,
            team_id=body.team_id,
            payload={
                **_build_athlete_payload(body=body),
                "photo_filename": photo.filename,
                "photo_mime_type": photo.content_type,
                "photo_content": await photo.read(),
            },
        )
        return result

    @router.put("/athletes", response_model=AthleteWriteResponse, status_code=200)
    async def update_athlete(
        body: Annotated[AthleteUpdateRequest, Depends(athlete_update_form_dependency)],
        photo: UploadFile | None = File(default=None),
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        payload: dict[str, Any] = _build_athlete_payload(
            body=body,
            athlete_id=body.athlete_id,
        )
        if photo is not None:
            payload.update(
                {
                    "photo_filename": photo.filename,
                    "photo_mime_type": photo.content_type,
                    "photo_content": await photo.read(),
                }
            )

        result = organization_team_service.update_athlete(
            user_id=user_id,
            org_id=body.org_id,
            team_id=body.team_id,
            payload=payload,
        )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "athlete_not_found"},
            )
        return result

    @router.get("/athletes", response_model=AthleteListResponse, status_code=200)
    def list_athletes(
        query: Annotated[AthleteListQuery, Depends()],
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_team_service.list_athletes(
            user_id=user_id,
            org_id=query.org_id,
            team_id=query.team_id,
        )
        return result

    @router.get("/athletes/photo/{athlete_id}", status_code=200)
    def get_athlete_photo(
        athlete_id: str,
        claims: dict[str, Any] = Depends(access_claims_dependency),
    ):
        user_id = claims.get("sub")
        result = organization_team_service.get_athlete_photo_by_id(
            user_id=user_id,
            athlete_id=athlete_id,
        )
        if result is None:
            return JSONResponse(
                status_code=404,
                content={"error": "athlete_not_found"},
            )
        content = result.get("content")
        if not isinstance(content, bytes):
            return JSONResponse(
                status_code=404,
                content={"error": "athlete_not_found"},
            )

        file_name = result.get("file_name")
        if not isinstance(file_name, str) or not file_name.strip():
            file_name = f"{athlete_id}.jpg"
        media_type = result.get("mime_type")
        if not isinstance(media_type, str) or not media_type.strip():
            media_type = "application/octet-stream"

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{file_name}"'},
        )

    return router


def _build_athlete_payload(
    *,
    body: AthleteCreateRequest | AthleteUpdateRequest,
    athlete_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "full_name": body.full_name,
        "birthday": body.birthday,
        "cpf": body.cpf,
        "cellphone": body.cellphone,
        "position": body.position.value,
        "tshirt_size": body.tshirt_size.value if body.tshirt_size else None,
        "shorts_size": body.shorts_size.value if body.shorts_size else None,
        "rg": body.rg,
        "email": body.email,
    }
    if athlete_id is not None:
        payload["athlete_id"] = athlete_id
    return payload

import os
import re

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse

from services.athlete_service import AthleteService

REQUIRED_FORM_FIELDS = (
    "team_folder_id",
    "full_name",
    "birthday",
    "cpf",
    "cellphone",
)


def create_athletes_router(athlete_service: AthleteService) -> APIRouter:
    athletes_router = APIRouter()

    @athletes_router.get("/athletes")
    def list_athletes(team_folder_id: str | None = Query(default=None)):
        result = athlete_service.list_athletes(team_folder_id)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    @athletes_router.post("/athletes")
    async def create_athlete(
        team_folder_id: str | None = Form(default=None),
        full_name: str | None = Form(default=None),
        birthday: str | None = Form(default=None),
        cpf: str | None = Form(default=None),
        cellphone: str | None = Form(default=None),
        tshirt_size: str | None = Form(default=None),
        shorts_size: str | None = Form(default=None),
        rg: str | None = Form(default=None),
        email: str | None = Form(default=None),
        photo: UploadFile | None = File(default=None),
    ):
        form_values = {
            "team_folder_id": team_folder_id,
            "full_name": full_name,
            "birthday": birthday,
            "cpf": cpf,
            "cellphone": cellphone,
        }
        missing_fields = [field for field in REQUIRED_FORM_FIELDS if not form_values.get(field)]
        if missing_fields:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "missing_required_fields",
                    "message": "Required fields are missing.",
                    "fields": missing_fields,
                },
            )

        if photo is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "missing_photo",
                    "message": "photo is required.",
                },
            )

        photo_filename = _secure_filename(photo.filename or "")
        if not photo_filename:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "invalid_photo",
                    "message": "photo must include a valid filename.",
                },
            )

        payload = {
            "team_folder_id": team_folder_id,
            "full_name": full_name,
            "birthday": birthday,
            "cpf": cpf,
            "cellphone": cellphone,
            "tshirt_size": tshirt_size,
            "shorts_size": shorts_size,
            "rg": rg,
            "email": email,
            "photo_filename": photo_filename,
            "photo_mime_type": photo.content_type,
            "photo_content": await photo.read(),
        }

        result = athlete_service.create_athlete(payload)

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=result)

    return athletes_router


_FILENAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


def _secure_filename(filename: str) -> str:
    normalized = filename.strip().replace("\\", "/")
    base_name = os.path.basename(normalized)
    sanitized = _FILENAME_SANITIZE_PATTERN.sub("_", base_name)
    return sanitized.strip("._")

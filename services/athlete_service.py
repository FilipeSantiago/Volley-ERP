from datetime import datetime, timezone
from typing import Any

from repositories.athlete_repository import (
    AthleteRepository,
    AthleteRepositoryError,
    TeamFolderAccessError,
)
from services.exceptions import (
    AthleteCreationError,
    InvalidAthletePayloadError,
    TeamFolderNotFoundError,
)

REQUIRED_FIELDS = ("team_folder_id", "full_name", "birthday", "cpf", "cellphone")
OPTIONAL_FIELDS = ("tshirt_size", "shorts_size", "rg", "email")


class AthleteService:
    def __init__(self, *, athlete_repository: AthleteRepository) -> None:
        self._athlete_repository = athlete_repository

    def create_athlete(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload = self._normalize_payload(payload)
        team_folder_id = normalized_payload["team_folder_id"]

        try:
            self._athlete_repository.ensure_team_folder_exists(
                team_folder_id=team_folder_id
            )
        except TeamFolderAccessError as error:
            raise TeamFolderNotFoundError(
                "Provided team_folder_id is invalid or inaccessible."
            ) from error
        except AthleteRepositoryError as error:
            raise AthleteCreationError("Failed to resolve team folder.") from error

        try:
            photos_folder = self._athlete_repository.get_or_create_photos_folder(
                team_folder_id=team_folder_id
            )
            uploaded_photo = self._athlete_repository.upload_photo(
                photos_folder_id=photos_folder["id"],
                file_name=normalized_payload["photo_filename"],
                file_content=normalized_payload["photo_content"],
                mime_type=normalized_payload["photo_mime_type"],
            )
        except AthleteRepositoryError as error:
            raise AthleteCreationError("Failed to upload athlete photo.") from error

        timestamp = self._current_timestamp()
        athlete_row = [
            normalized_payload["full_name"],
            normalized_payload["birthday"],
            normalized_payload["cpf"],
            normalized_payload["cellphone"],
            normalized_payload["tshirt_size"] or "",
            normalized_payload["shorts_size"] or "",
            normalized_payload["rg"] or "",
            normalized_payload["email"] or "",
            uploaded_photo.get("webViewLink") or "",
            timestamp,
            timestamp,
        ]

        try:
            sheet_info = self._athlete_repository.append_to_team_athletes_sheet(
                team_folder_id=team_folder_id,
                athlete_row=athlete_row,
            )
        except AthleteRepositoryError as error:
            raise AthleteCreationError("Failed to save athlete data in sheet.") from error

        return {
            "team_folder_id": team_folder_id,
            "full_name": normalized_payload["full_name"],
            "birthday": normalized_payload["birthday"],
            "cpf": normalized_payload["cpf"],
            "cellphone": normalized_payload["cellphone"],
            "tshirt_size": normalized_payload["tshirt_size"],
            "shorts_size": normalized_payload["shorts_size"],
            "rg": normalized_payload["rg"],
            "email": normalized_payload["email"],
            "photo_link": uploaded_photo.get("webViewLink"),
            "photos_folder_id": photos_folder["id"],
            "athletes_sheet_id": sheet_info["spreadsheet_id"],
            "created_at": timestamp,
            "updated_at": timestamp,
        }

    def list_athletes(self, team_folder_id: Any) -> dict[str, Any]:
        normalized_team_folder_id = self._normalize_team_folder_id(team_folder_id)
        try:
            self._athlete_repository.ensure_team_folder_exists(
                team_folder_id=normalized_team_folder_id
            )
        except TeamFolderAccessError as error:
            raise TeamFolderNotFoundError(
                "Provided team_folder_id is invalid or inaccessible."
            ) from error
        except AthleteRepositoryError as error:
            raise AthleteCreationError("Failed to resolve team folder.") from error

        try:
            list_result = self._athlete_repository.list_team_athletes(
                team_folder_id=normalized_team_folder_id
            )
        except AthleteRepositoryError as error:
            raise AthleteCreationError("Failed to list team athletes.") from error

        items = list_result["items"]
        return {
            "team_folder_id": normalized_team_folder_id,
            "athletes_sheet_id": list_result["spreadsheet_id"],
            "items": items,
            "count": len(items),
        }

    @staticmethod
    def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload: dict[str, Any] = {}

        for field in REQUIRED_FIELDS:
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise InvalidAthletePayloadError(
                    f"{field} is required and must be a non-empty string."
                )
            normalized_payload[field] = value.strip()

        for field in OPTIONAL_FIELDS:
            value = payload.get(field)
            if value is None:
                normalized_payload[field] = None
                continue
            if not isinstance(value, str):
                raise InvalidAthletePayloadError(f"{field} must be a string when provided.")
            stripped = value.strip()
            normalized_payload[field] = stripped if stripped else None

        photo_content = payload.get("photo_content")
        if not isinstance(photo_content, bytes) or len(photo_content) == 0:
            raise InvalidAthletePayloadError("photo is required and must be a non-empty file.")

        photo_filename = payload.get("photo_filename")
        if not isinstance(photo_filename, str) or not photo_filename.strip():
            raise InvalidAthletePayloadError("photo filename is required.")

        photo_mime_type = payload.get("photo_mime_type")
        if photo_mime_type is not None and not isinstance(photo_mime_type, str):
            raise InvalidAthletePayloadError("photo mimetype must be a string when provided.")

        normalized_payload["photo_content"] = photo_content
        normalized_payload["photo_filename"] = photo_filename.strip()
        normalized_payload["photo_mime_type"] = (
            photo_mime_type.strip() if isinstance(photo_mime_type, str) else None
        )

        return normalized_payload

    @staticmethod
    def _current_timestamp() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )

    @staticmethod
    def _normalize_team_folder_id(team_folder_id: Any) -> str:
        if not isinstance(team_folder_id, str) or not team_folder_id.strip():
            raise InvalidAthletePayloadError(
                "team_folder_id is required and must be a non-empty string."
            )
        return team_folder_id.strip()

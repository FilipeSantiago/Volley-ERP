import unittest

from repositories.athlete_repository import AthleteRepositoryError, TeamFolderAccessError
from services.athlete_service import AthleteService
from services.exceptions import (
    AthleteCreationError,
    InvalidAthletePayloadError,
    TeamFolderNotFoundError,
)


class FakeAthleteRepository:
    def __init__(self) -> None:
        self.raise_team_access_error = False
        self.raise_upload_error = False
        self.raise_append_error = False
        self.raise_list_error = False
        self.list_result = {"spreadsheet_id": "athletes-sheet-id", "items": []}
        self.last_listed_team_folder_id = None
        self.last_uploaded = None
        self.last_appended_row = None

    def ensure_team_folder_exists(self, *, team_folder_id: str):
        if self.raise_team_access_error:
            raise TeamFolderAccessError("invalid team folder")
        return {"id": team_folder_id, "name": "Team A"}

    def get_or_create_photos_folder(self, *, team_folder_id: str):
        return {"id": "photos-folder-id", "name": "photos"}

    def upload_photo(
        self,
        *,
        photos_folder_id: str,
        file_name: str,
        file_content: bytes,
        mime_type: str | None,
    ):
        if self.raise_upload_error:
            raise AthleteRepositoryError("upload failed")

        self.last_uploaded = {
            "photos_folder_id": photos_folder_id,
            "file_name": file_name,
            "file_content": file_content,
            "mime_type": mime_type,
        }
        return {"id": "photo-file-id", "webViewLink": "https://drive.test/photo-link"}

    def append_to_team_athletes_sheet(self, *, team_folder_id: str, athlete_row: list[str]):
        if self.raise_append_error:
            raise AthleteRepositoryError("append failed")

        self.last_appended_row = athlete_row
        return {"spreadsheet_id": "athletes-sheet-id", "sheet_title": "Athletes"}

    def list_team_athletes(self, *, team_folder_id: str):
        if self.raise_list_error:
            raise AthleteRepositoryError("list failed")
        self.last_listed_team_folder_id = team_folder_id
        return dict(self.list_result)


class AthleteServiceTestCase(unittest.TestCase):
    def test_list_athletes_success(self):
        repository = FakeAthleteRepository()
        repository.list_result = {
            "spreadsheet_id": "athletes-sheet-id",
            "items": [
                {
                    "full_name": "Jane Doe",
                    "birthday": "2000-01-01",
                    "cpf": "12345678900",
                    "cellphone": "5511999999999",
                    "tshirt_size": "M",
                    "shorts_size": "G",
                    "rg": "",
                    "email": "jane@example.com",
                    "photo_link": "https://drive.test/photo-link",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
        }
        service = AthleteService(athlete_repository=repository)

        result = service.list_athletes("team-folder-id")

        self.assertEqual(result["team_folder_id"], "team-folder-id")
        self.assertEqual(result["athletes_sheet_id"], "athletes-sheet-id")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["full_name"], "Jane Doe")
        self.assertEqual(repository.last_listed_team_folder_id, "team-folder-id")

    def test_list_athletes_requires_team_folder_id(self):
        repository = FakeAthleteRepository()
        service = AthleteService(athlete_repository=repository)

        with self.assertRaises(InvalidAthletePayloadError):
            service.list_athletes("   ")

    def test_list_athletes_raises_not_found_for_invalid_team_folder(self):
        repository = FakeAthleteRepository()
        repository.raise_team_access_error = True
        service = AthleteService(athlete_repository=repository)

        with self.assertRaises(TeamFolderNotFoundError):
            service.list_athletes("invalid-team-folder-id")

    def test_list_athletes_raises_creation_error_on_repository_failure(self):
        repository = FakeAthleteRepository()
        repository.raise_list_error = True
        service = AthleteService(athlete_repository=repository)

        with self.assertRaises(AthleteCreationError):
            service.list_athletes("team-folder-id")

    def test_create_athlete_success(self):
        repository = FakeAthleteRepository()
        service = AthleteService(athlete_repository=repository)
        payload = {
            "team_folder_id": "team-folder-id",
            "full_name": "Jane Doe",
            "birthday": "2000-01-01",
            "cpf": "12345678900",
            "cellphone": "5511999999999",
            "tshirt_size": "M",
            "shorts_size": "G",
            "rg": None,
            "email": "jane@example.com",
            "photo_filename": "jane.jpg",
            "photo_mime_type": "image/jpeg",
            "photo_content": b"binary-image",
        }

        result = service.create_athlete(payload)

        self.assertEqual(result["team_folder_id"], "team-folder-id")
        self.assertEqual(result["full_name"], "Jane Doe")
        self.assertEqual(result["rg"], None)
        self.assertEqual(result["photo_link"], "https://drive.test/photo-link")
        self.assertEqual(result["photos_folder_id"], "photos-folder-id")
        self.assertEqual(result["athletes_sheet_id"], "athletes-sheet-id")
        self.assertEqual(result["created_at"], result["updated_at"])
        self.assertTrue(result["created_at"].endswith("Z"))
        self.assertEqual(repository.last_uploaded["file_name"], "jane.jpg")
        self.assertEqual(repository.last_appended_row[6], "")

    def test_create_athlete_requires_required_fields(self):
        repository = FakeAthleteRepository()
        service = AthleteService(athlete_repository=repository)
        payload = {
            "team_folder_id": "team-folder-id",
            "full_name": "",
            "birthday": "2000-01-01",
            "cpf": "12345678900",
            "cellphone": "5511999999999",
            "photo_filename": "jane.jpg",
            "photo_mime_type": "image/jpeg",
            "photo_content": b"binary-image",
        }

        with self.assertRaises(InvalidAthletePayloadError):
            service.create_athlete(payload)

    def test_create_athlete_requires_non_empty_photo(self):
        repository = FakeAthleteRepository()
        service = AthleteService(athlete_repository=repository)
        payload = {
            "team_folder_id": "team-folder-id",
            "full_name": "Jane Doe",
            "birthday": "2000-01-01",
            "cpf": "12345678900",
            "cellphone": "5511999999999",
            "photo_filename": "jane.jpg",
            "photo_mime_type": "image/jpeg",
            "photo_content": b"",
        }

        with self.assertRaises(InvalidAthletePayloadError):
            service.create_athlete(payload)

    def test_create_athlete_raises_not_found_for_invalid_team_folder(self):
        repository = FakeAthleteRepository()
        repository.raise_team_access_error = True
        service = AthleteService(athlete_repository=repository)
        payload = {
            "team_folder_id": "invalid-team-folder-id",
            "full_name": "Jane Doe",
            "birthday": "2000-01-01",
            "cpf": "12345678900",
            "cellphone": "5511999999999",
            "photo_filename": "jane.jpg",
            "photo_mime_type": "image/jpeg",
            "photo_content": b"binary-image",
        }

        with self.assertRaises(TeamFolderNotFoundError):
            service.create_athlete(payload)

    def test_create_athlete_raises_creation_error_on_repository_failure(self):
        repository = FakeAthleteRepository()
        repository.raise_append_error = True
        service = AthleteService(athlete_repository=repository)
        payload = {
            "team_folder_id": "team-folder-id",
            "full_name": "Jane Doe",
            "birthday": "2000-01-01",
            "cpf": "12345678900",
            "cellphone": "5511999999999",
            "photo_filename": "jane.jpg",
            "photo_mime_type": "image/jpeg",
            "photo_content": b"binary-image",
        }

        with self.assertRaises(AthleteCreationError):
            service.create_athlete(payload)


if __name__ == "__main__":
    unittest.main()

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.athlete_controller import create_athletes_router
from controllers.exception_handlers import register_exception_handlers
from services.exceptions import (
    AthleteCreationError,
    InvalidAthletePayloadError,
    TeamFolderNotFoundError,
)


class FakeAthleteService:
    def __init__(self) -> None:
        self.result = {"ok": True}
        self.error = None
        self.received_payload = None
        self.received_team_folder_id = None

    def create_athlete(self, payload):
        self.received_payload = payload
        if self.error is not None:
            raise self.error
        return self.result

    def list_athletes(self, team_folder_id):
        self.received_team_folder_id = team_folder_id
        if self.error is not None:
            raise self.error
        return self.result


class AthleteControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.athlete_service = FakeAthleteService()
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(create_athletes_router(self.athlete_service))
        self.client = TestClient(app)

    def test_create_athlete_requires_required_fields(self):
        response = self.client.post(
            "/athletes",
            data={
                "full_name": "Jane Doe",
                "birthday": "2000-01-01",
                "cpf": "12345678900",
                "cellphone": "5511999999999",
            },
            files={"photo": ("photo.jpg", b"img", "image/jpeg")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "missing_required_fields")
        self.assertIn("team_folder_id", response.json()["fields"])

    def test_list_athletes_success(self):
        self.athlete_service.result = {"items": [], "count": 0}

        response = self.client.get("/athletes?team_folder_id=team-folder-id")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [], "count": 0})
        self.assertEqual(self.athlete_service.received_team_folder_id, "team-folder-id")

    def test_list_athletes_maps_service_errors(self):
        test_cases = [
            (InvalidAthletePayloadError("invalid"), 400, "invalid_athlete_payload"),
            (TeamFolderNotFoundError("not found"), 404, "team_folder_not_found"),
            (AthleteCreationError("failed"), 502, "athlete_creation_failed"),
        ]
        for error, expected_status, expected_code in test_cases:
            self.athlete_service.error = error
            response = self.client.get("/athletes?team_folder_id=team-folder-id")
            self.assertEqual(response.status_code, expected_status)
            self.assertEqual(response.json()["error"], expected_code)

    def test_create_athlete_requires_photo(self):
        response = self.client.post(
            "/athletes",
            data={
                "team_folder_id": "team-folder-id",
                "full_name": "Jane Doe",
                "birthday": "2000-01-01",
                "cpf": "12345678900",
                "cellphone": "5511999999999",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "missing_photo")

    def test_create_athlete_success(self):
        self.athlete_service.result = {"athlete_id": "1"}
        response = self.client.post(
            "/athletes",
            data={
                "team_folder_id": "team-folder-id",
                "full_name": "Jane Doe",
                "birthday": "2000-01-01",
                "cpf": "12345678900",
                "cellphone": "5511999999999",
            },
            files={"photo": ("photo.jpg", b"img", "image/jpeg")},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"athlete_id": "1"})
        self.assertEqual(
            self.athlete_service.received_payload["team_folder_id"], "team-folder-id"
        )
        self.assertEqual(self.athlete_service.received_payload["photo_filename"], "photo.jpg")
        self.assertEqual(self.athlete_service.received_payload["photo_content"], b"img")

    def test_create_athlete_maps_service_errors(self):
        test_cases = [
            (InvalidAthletePayloadError("invalid"), 400, "invalid_athlete_payload"),
            (TeamFolderNotFoundError("not found"), 404, "team_folder_not_found"),
            (AthleteCreationError("failed"), 502, "athlete_creation_failed"),
        ]
        for error, expected_status, expected_code in test_cases:
            self.athlete_service.error = error
            response = self.client.post(
                "/athletes",
                data={
                    "team_folder_id": "team-folder-id",
                    "full_name": "Jane Doe",
                    "birthday": "2000-01-01",
                    "cpf": "12345678900",
                    "cellphone": "5511999999999",
                },
                files={"photo": ("photo.jpg", b"img", "image/jpeg")},
            )
            self.assertEqual(response.status_code, expected_status)
            self.assertEqual(response.json()["error"], expected_code)


if __name__ == "__main__":
    unittest.main()

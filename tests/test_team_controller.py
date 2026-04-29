import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.exception_handlers import register_exception_handlers
from controllers.team_controller import create_teams_router
from services.exceptions import (
    InvalidTeamNameError,
    RootFolderNotConfiguredError,
    TeamAlreadyExistsError,
    TeamCreationError,
)


class FakeTeamService:
    def __init__(self) -> None:
        self.result = {"ok": True}
        self.error = None
        self.received_team_name = None

    def list_teams(self):
        if self.error is not None:
            raise self.error
        return self.result

    def create_team(self, team_name):
        self.received_team_name = team_name
        if self.error is not None:
            raise self.error
        return self.result


class TeamControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.team_service = FakeTeamService()
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(create_teams_router(self.team_service))
        self.client = TestClient(app)

    def test_list_teams_success(self):
        self.team_service.result = {"items": [], "count": 0}

        response = self.client.get("/teams")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": [], "count": 0})

    def test_list_teams_maps_service_errors(self):
        test_cases = [
            (
                RootFolderNotConfiguredError("not configured"),
                500,
                "root_folder_not_configured",
            ),
            (TeamCreationError("failed"), 502, "team_creation_failed"),
        ]
        for error, expected_status, expected_code in test_cases:
            self.team_service.error = error
            response = self.client.get("/teams")
            self.assertEqual(response.status_code, expected_status)
            self.assertEqual(response.json()["error"], expected_code)

    def test_create_team_requires_valid_json(self):
        response = self.client.post(
            "/teams",
            data="not-json",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "invalid_json")

    def test_create_team_success(self):
        self.team_service.result = {"team_folder_id": "team-folder-id"}

        response = self.client.post("/teams", json={"team_name": "Team A"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"team_folder_id": "team-folder-id"})
        self.assertEqual(self.team_service.received_team_name, "Team A")

    def test_create_team_maps_service_errors(self):
        test_cases = [
            (InvalidTeamNameError("invalid"), 400, "invalid_team_name"),
            (
                TeamAlreadyExistsError(
                    team_name="Team A",
                    team_folder_id="team-folder-id",
                ),
                409,
                "team_already_exists",
            ),
            (TeamCreationError("failed"), 502, "team_creation_failed"),
        ]
        for error, expected_status, expected_code in test_cases:
            self.team_service.error = error
            response = self.client.post("/teams", json={"team_name": "Team A"})
            self.assertEqual(response.status_code, expected_status)
            self.assertEqual(response.json()["error"], expected_code)


if __name__ == "__main__":
    unittest.main()

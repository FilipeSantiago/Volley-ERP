import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.exception_handlers import register_exception_handlers
from controllers.team_controller import create_teams_router
from services.security.auth_exceptions import InvalidTokenError
from services.security.auth_guard import AuthGuard


class FakeAuthServiceForGuard:
    def validate_access_token(self, *, access_token: str):
        if access_token == "valid-token":
            return {"sub": "user-1", "email": "user@example.com", "google_sub": "g-1"}
        raise InvalidTokenError("invalid_token")


class FakeOrganizationTeamService:
    def create_team(self, *, user_id: str, org_id: str, payload: dict):
        return {"team_id": "team-1", "name": payload["name"], "status": "active", "org_id": org_id}

    def list_teams(self, *, user_id: str, org_id: str):
        return {"items": [{"team_id": "team-1", "name": "Team One"}], "count": 1, "org_id": org_id}

    def get_team(self, *, user_id: str, org_id: str, team_id: str):
        return {"team_id": team_id, "name": "Team One", "status": "active", "org_id": org_id}

    def add_team_member(self, *, user_id: str, org_id: str, team_id: str, payload: dict):
        return {"status": "ok", "org_id": org_id, "team_id": team_id, "team_role": payload["team_role"]}

    def list_team_members(self, *, user_id: str, org_id: str, team_id: str):
        return {"items": [{"user_id": "user-2"}], "count": 1, "org_id": org_id, "team_id": team_id}


class TeamControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        auth_guard = AuthGuard(auth_service=FakeAuthServiceForGuard())
        app.include_router(create_teams_router(FakeOrganizationTeamService(), auth_guard))
        self.client = TestClient(app)

    def test_teams_endpoint_is_protected(self):
        response = self.client.get("/teams", params={"org_id": "org-1"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_create_team_success(self):
        response = self.client.post(
            "/teams",
            json={"org_id": "org-1", "name": "Team One"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["team_id"], "team-1")

    def test_list_teams_requires_org_id(self):
        response = self.client.get(
            "/teams",
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

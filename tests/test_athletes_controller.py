import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.athletes_controller import create_athletes_router
from controllers.exception_handlers import register_exception_handlers
from services.security.auth_exceptions import InvalidTokenError
from services.security.auth_guard import AuthGuard


class FakeAuthServiceForGuard:
    def validate_access_token(self, *, access_token: str):
        if access_token == "valid-token":
            return {"sub": "user-1", "email": "user@example.com", "google_sub": "g-1"}
        raise InvalidTokenError("invalid_token")


class FakeOrganizationTeamService:
    def create_athlete(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict,
    ):
        return {
            "org_id": org_id,
            "team_id": team_id,
            "athletes_sheet_id": "sheet-1",
            "athlete_id": "athlete-1",
            "full_name": payload["full_name"],
            "birthday": payload["birthday"],
            "cpf": payload["cpf"],
            "cellphone": payload["cellphone"],
            "position": payload["position"],
        }

    def list_athletes(self, *, user_id: str, org_id: str, team_id: str | None = None):
        return {"org_id": org_id, "team_id": team_id, "items": [], "count": 0}

    def update_athlete(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict,
    ):
        if payload["athlete_id"] == "missing":
            return None
        return {
            "org_id": org_id,
            "team_id": team_id,
            "athletes_sheet_id": "sheet-1",
            "athlete_id": payload["athlete_id"],
            "full_name": payload["full_name"],
            "birthday": payload["birthday"],
            "cpf": payload["cpf"],
            "cellphone": payload["cellphone"],
            "position": payload["position"],
            "photo_link": "https://drive.google.com/file/d/new-photo/view",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }

    def get_athlete_photo_by_id(self, *, user_id: str, athlete_id: str):
        if athlete_id == "athlete-1":
            return {
                "athlete_id": athlete_id,
                "content": b"fake-image",
                "mime_type": "image/jpeg",
                "file_name": "athlete-1.jpg",
            }
        return None


class AthletesControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        auth_guard = AuthGuard(auth_service=FakeAuthServiceForGuard())
        app.include_router(create_athletes_router(FakeOrganizationTeamService(), auth_guard))
        self.client = TestClient(app)

    def test_athletes_endpoint_is_protected(self):
        response = self.client.get("/athletes", params={"org_id": "org-1", "team_id": "team-1"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_create_athlete_requires_photo(self):
        response = self.client.post(
            "/athletes",
            data={
                "org_id": "org-1",
                "team_id": "team-1",
                "full_name": "John Doe",
                "birthday": "2001-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
            },
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "missing_photo")

    def test_create_athlete_success(self):
        response = self.client.post(
            "/athletes",
            data={
                "org_id": "org-1",
                "team_id": "team-1",
                "full_name": "John Doe",
                "birthday": "2001-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
            },
            files={"photo": ("john.jpg", b"fake-image", "image/jpeg")},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["athletes_sheet_id"], "sheet-1")

    def test_list_athletes_requires_query_params(self):
        response = self.client.get(
            "/athletes",
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 422)

    def test_list_athletes_allows_missing_team_id(self):
        response = self.client.get(
            "/athletes",
            params={"org_id": "org-1"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["team_id"])

    def test_update_athlete_success(self):
        response = self.client.put(
            "/athletes",
            data={
                "org_id": "org-1",
                "team_id": "team-1",
                "athlete_id": "athlete-1",
                "full_name": "John Doe Updated",
                "birthday": "2001-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
            },
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["athlete_id"], "athlete-1")
        self.assertEqual(response.json()["athletes_sheet_id"], "sheet-1")

    def test_update_athlete_not_found(self):
        response = self.client.put(
            "/athletes",
            data={
                "org_id": "org-1",
                "team_id": "team-1",
                "athlete_id": "missing",
                "full_name": "John Doe Updated",
                "birthday": "2001-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
            },
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "athlete_not_found")

    def test_get_athlete_photo_success(self):
        response = self.client.get(
            "/athletes/photo/athlete-1",
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.content, b"fake-image")

    def test_get_athlete_photo_not_found(self):
        response = self.client.get(
            "/athletes/photo/missing",
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "athlete_not_found")


if __name__ == "__main__":
    unittest.main()

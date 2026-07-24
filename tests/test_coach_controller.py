import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.coach_controller import create_coach_router
from controllers.exception_handlers import register_exception_handlers
from services.security.auth_exceptions import InvalidTokenError
from services.security.auth_guard import AuthGuard


class FakeAuthServiceForGuard:
    def validate_access_token(self, *, access_token: str):
        if access_token == "valid-token":
            return {"sub": "user-1", "email": "user@example.com", "google_sub": "g-1"}
        raise InvalidTokenError("invalid_token")


class FakeCoachService:
    def create_coach(
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
            "coach_sheet_id": "sheet-1",
            "coach_sheet_url": "https://sheet",
            "full_name": payload["full_name"],
            "birthday": payload["birthday"],
            "cpf": payload["cpf"],
            "cellphone": payload["cellphone"],
            "position": payload["position"],
            "pix_key": payload["pix_key"],
            "photo_link": "https://drive.google.com/file/d/coach-photo/view",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

    def update_coach(
        self,
        *,
        user_id: str,
        org_id: str,
        team_id: str,
        payload: dict,
    ):
        if payload.get("full_name") == "Missing Coach":
            return None
        return {
            "org_id": org_id,
            "team_id": team_id,
            "coach_sheet_id": "sheet-1",
            "coach_sheet_url": "https://sheet",
            "full_name": payload["full_name"],
            "birthday": payload["birthday"],
            "cpf": payload["cpf"],
            "cellphone": payload["cellphone"],
            "position": payload["position"],
            "pix_key": payload["pix_key"],
            "photo_link": "https://drive.google.com/file/d/coach-photo/view",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }

    def get_coach(self, *, user_id: str, org_id: str, team_id: str):
        if team_id == "missing":
            return None
        return {
            "org_id": org_id,
            "team_id": team_id,
            "coach_sheet_id": "sheet-1",
            "coach_sheet_url": "https://sheet",
            "full_name": "Coach One",
            "birthday": "1980-01-01",
            "cpf": "123",
            "cellphone": "555-0101",
            "position": "Central",
            "pix_key": "coach@pix",
            "photo_link": "https://drive.google.com/file/d/coach-photo/view",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }

    def get_coach_photo(self, *, user_id: str, org_id: str, team_id: str):
        if team_id == "missing":
            return None
        return {
            "content": b"fake-image",
            "mime_type": "image/jpeg",
            "file_name": "coach.jpg",
            "full_name": "Coach One",
            "org_id": org_id,
            "team_id": team_id,
        }


class CoachControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        auth_guard = AuthGuard(auth_service=FakeAuthServiceForGuard())
        app.include_router(create_coach_router(FakeCoachService(), auth_guard))
        self.client = TestClient(app)

    def test_coach_endpoint_is_protected(self):
        response = self.client.get("/coach", params={"org_id": "org-1", "team_id": "team-1"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_create_coach_requires_photo(self):
        response = self.client.post(
            "/coach",
            data={
                "org_id": "org-1",
                "team_id": "team-1",
                "full_name": "Coach One",
                "birthday": "1980-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
                "pix_key": "coach@pix",
            },
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "missing_photo")

    def test_create_coach_success(self):
        response = self.client.post(
            "/coach",
            data={
                "org_id": "org-1",
                "team_id": "team-1",
                "full_name": "Coach One",
                "birthday": "1980-01-01",
                "cpf": "123",
                "cellphone": "555-0101",
                "position": "Central",
                "pix_key": "coach@pix",
            },
            files={"photo": ("coach.jpg", b"fake-image", "image/jpeg")},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["coach_sheet_id"], "sheet-1")

    def test_get_coach_not_found(self):
        response = self.client.get(
            "/coach",
            params={"org_id": "org-1", "team_id": "missing"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "coach_not_found")

    def test_get_coach_photo_success(self):
        response = self.client.get(
            "/coach/photo",
            params={"org_id": "org-1", "team_id": "team-1"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.content, b"fake-image")


if __name__ == "__main__":
    unittest.main()

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.customer_controller import create_customer_router
from controllers.exception_handlers import register_exception_handlers
from services.security.auth_exceptions import InvalidTokenError
from services.security.auth_guard import AuthGuard


class FakeAuthServiceForGuard:
    def validate_access_token(self, *, access_token: str):
        if access_token == "valid-token":
            return {
                "sub": "customer-1",
                "google_sub": "google-sub-1",
                "email": "person@example.com",
                "doc_id": "doc-1",
            }
        raise InvalidTokenError("invalid_token")


class FakeCustomerService:
    def create_workspace(self, *, customer_id: str, workspace_name: str | None):
        return {
            "status": "ok",
            "customer_id": customer_id,
            "doc_id": "doc-2",
            "workspace_folder_id": "folder-1",
            "workspace_folder_link": "https://drive.google.com/folder-1",
            "doc_link": "https://docs.google.com/spreadsheets/d/doc-2",
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "token_type": "Bearer",
            "expires_in": 600,
        }


class CustomerWorkspaceControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        auth_guard = AuthGuard(auth_service=FakeAuthServiceForGuard())
        app.include_router(create_customer_router(FakeCustomerService(), auth_guard))

        self.client = TestClient(app)

    def test_workspace_endpoint_is_protected(self):
        response = self.client.post("/customer/workspace", json={})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")

    def test_workspace_endpoint_returns_reissued_tokens(self):
        response = self.client.post(
            "/customer/workspace",
            json={"workspace_name": "Team Workspace"},
            headers={"Authorization": "Bearer valid-token"},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["token_type"], "Bearer")
        self.assertIn("access_token", payload)
        self.assertIn("refresh_token", payload)
        self.assertIn("expires_in", payload)


if __name__ == "__main__":
    unittest.main()

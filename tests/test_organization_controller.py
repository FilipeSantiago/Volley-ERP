import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.exception_handlers import register_exception_handlers
from controllers.organization_controller import create_organizations_router
from services.security.auth_exceptions import InvalidTokenError
from services.security.auth_guard import AuthGuard


class FakeAuthServiceForGuard:
    def validate_access_token(self, *, access_token: str):
        if access_token == "valid-token":
            return {"sub": "user-1", "email": "user@example.com", "google_sub": "g-1"}
        raise InvalidTokenError("invalid_token")


class FakeOrganizationService:
    def create_organization(self, *, user_id: str, payload: dict):
        return {
            "org_id": "org-1",
            "name": payload["name"],
            "org_role": "OWNER",
            "workspace_status": "provisioned",
        }

    def list_organizations(self, *, user_id: str):
        return [{"org_id": "org-1", "name": "Org One", "org_role": "OWNER", "status": "active", "can_access_all_teams": True, "teams": []}]

    def get_organization(self, *, user_id: str, org_id: str):
        return {"org_id": org_id, "name": "Org One", "org_role": "OWNER", "status": "active", "can_access_all_teams": True, "teams": []}

    def ensure_workspace(self, *, user_id: str, org_id: str):
        return {"status": "ok", "org_id": org_id, "workspace_root_folder_id": "root-1", "workspace_sheets_folder_id": "sheets-1", "workspace_images_folder_id": "images-1", "workspace_exports_folder_id": "exports-1"}

    def list_members(self, *, user_id: str, org_id: str):
        return {"items": [], "count": 0}

    def remove_member(self, *, requester_user_id: str, org_id: str, target_user_id: str):
        return {"status": "ok", "org_id": org_id, "user_id": target_user_id, "member_status": "inactive"}


class FakeInviteService:
    def create_invite(self, *, user_id: str, org_id: str, payload: dict):
        return {"invite_id": "invite-1", "invite_url": "https://app.test/invite/accept?token=abc", "expires_at": "2099-01-01T00:00:00Z"}

    def accept_invite(self, *, user_id: str, token: str):
        return {"status": "ok", "org_id": "org-1", "team_id": "team-1", "team_role": "PLAYER"}


class OrganizationControllerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app = FastAPI()
        register_exception_handlers(app)
        auth_guard = AuthGuard(auth_service=FakeAuthServiceForGuard())
        app.include_router(
            create_organizations_router(
                FakeOrganizationService(),
                FakeInviteService(),
                auth_guard,
            )
        )
        self.client = TestClient(app)

    def test_organizations_endpoint_is_protected(self):
        response = self.client.get("/organizations")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "unauthorized")

    def test_create_organization_success(self):
        response = self.client.post(
            "/organizations",
            json={"name": "Org One"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["org_id"], "org-1")

    def test_accept_invite_success(self):
        response = self.client.post(
            "/organizations/invites/accept",
            json={"token": "abc"},
            headers={"Authorization": "Bearer valid-token"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()

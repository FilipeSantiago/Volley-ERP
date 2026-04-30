import unittest

from services.organization_service import OrganizationService
from services.security.auth_exceptions import StorageOwnerConnectionMissingError


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.orgs = {}
        self.user_orgs = {}
        self.teams = {}

    def create_organization_with_owner(self, *, name: str, owner_user_id: str, owner_email: str | None):
        org = {
            "org_id": "org-1",
            "name": name,
            "owner_user_id": owner_user_id,
            "storage_owner_user_id": owner_user_id,
        }
        self.orgs["org-1"] = org
        self.user_orgs.setdefault(owner_user_id, []).append(
            {
                "org_id": "org-1",
                "org_name": name,
                "org_role": "OWNER",
                "status": "active",
            }
        )
        return dict(org)

    def list_user_organizations(self, *, user_id: str):
        return list(self.user_orgs.get(user_id, []))

    def list_teams_for_org(self, *, org_id: str):
        return list(self.teams.get(org_id, []))

    def list_user_team_pointers(self, *, user_id: str, org_id: str):
        return []

    def get_organization(self, *, org_id: str):
        org = self.orgs.get(org_id)
        return dict(org) if org else None

    def list_org_members(self, *, org_id: str):
        return []

    def set_org_member_status(self, *, org_id: str, user_id: str, status: str):
        return {"user_id": user_id, "status": status}


class FakeGoogleConnectionRepository:
    def __init__(self, has_connection: bool = True) -> None:
        self.has_connection = has_connection

    def get_by_user_id(self, *, user_id: str):
        if not self.has_connection:
            return None
        return {
            "provider": "google",
            "encrypted_refresh_token": "enc",
            "scopes": [
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/spreadsheets",
            ],
        }


class FakeAuthorizationService:
    def require_org_member(self, *, user_id: str, org_id: str):
        return {"org_role": "OWNER", "status": "active"}

    def require_org_permission(self, *, user_id: str, org_id: str, permission: str):
        return {"org_role": "OWNER", "status": "active"}

    def can_access_all_teams(self, *, user_id: str, org_id: str):
        return True


class FakeUserRepository:
    def get_by_user_id(self, *, user_id: str):
        return {
            "user_id": user_id,
            "email": "owner@example.com",
        }


class FakeWorkspaceService:
    def __init__(self) -> None:
        self.provision_calls = []
        self.ensure_calls = []

    def provision_workspace_for_new_organization(self, *, org_id: str, storage_owner_user_id: str):
        self.provision_calls.append((org_id, storage_owner_user_id))
        return {
            "workspace_root_folder_id": "root-1",
            "workspace_sheets_folder_id": "sheets-1",
            "workspace_images_folder_id": "images-1",
            "workspace_exports_folder_id": "exports-1",
        }

    def ensure_workspace_for_organization(self, *, org_id: str):
        self.ensure_calls.append(org_id)
        return {
            "workspace_root_folder_id": "root-1",
            "workspace_sheets_folder_id": "sheets-1",
            "workspace_images_folder_id": "images-1",
            "workspace_exports_folder_id": "exports-1",
        }


class OrganizationServiceTestCase(unittest.TestCase):
    def test_create_organization_provisions_workspace(self):
        repo = FakeOrganizationRepository()
        service = OrganizationService(
            organization_repository=repo,
            user_repository=FakeUserRepository(),
            google_connection_repository=FakeGoogleConnectionRepository(has_connection=True),
            authorization_service=FakeAuthorizationService(),
            workspace_service=FakeWorkspaceService(),
        )

        result = service.create_organization(user_id="user-1", payload={"name": "Org One"})
        self.assertEqual(result["org_id"], "org-1")
        self.assertEqual(result["workspace_status"], "provisioned")

    def test_create_organization_requires_google_connection(self):
        repo = FakeOrganizationRepository()
        service = OrganizationService(
            organization_repository=repo,
            user_repository=FakeUserRepository(),
            google_connection_repository=FakeGoogleConnectionRepository(has_connection=False),
            authorization_service=FakeAuthorizationService(),
            workspace_service=FakeWorkspaceService(),
        )
        with self.assertRaises(StorageOwnerConnectionMissingError):
            service.create_organization(user_id="user-1", payload={"name": "Org One"})

    def test_list_organizations_ignores_inactive_memberships(self):
        repo = FakeOrganizationRepository()
        repo.user_orgs["user-1"] = [
            {
                "org_id": "org-active",
                "org_name": "Active Org",
                "org_role": "OWNER",
                "status": "active",
            },
            {
                "org_id": "org-inactive",
                "org_name": "Inactive Org",
                "org_role": "MEMBER",
                "status": "inactive",
            },
        ]
        service = OrganizationService(
            organization_repository=repo,
            user_repository=FakeUserRepository(),
            google_connection_repository=FakeGoogleConnectionRepository(has_connection=True),
            authorization_service=FakeAuthorizationService(),
            workspace_service=FakeWorkspaceService(),
        )
        organizations = service.list_organizations(user_id="user-1")
        self.assertEqual(len(organizations), 1)
        self.assertEqual(organizations[0]["org_id"], "org-active")


if __name__ == "__main__":
    unittest.main()

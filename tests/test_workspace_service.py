import unittest

from repositories.google_drive_repository import GoogleDriveRepositoryError
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import (
    StorageOwnerConnectionMissingError,
    WorkspaceProvisioningFailedError,
)
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)
from services.workspace_service import WorkspaceService


def _build_auth_config() -> AuthConfig:
    return AuthConfig(
        google_oauth_client_id="web-client-id",
        google_oauth_client_secret="web-client-secret",
        google_oauth_redirect_uri="https://api.example.com/auth/google/callback",
        google_oauth_android_client_id="android-client-id",
        google_oauth_android_client_secret="android-client-secret",
        google_oauth_ios_client_id="ios-client-id",
        google_oauth_ios_client_secret="ios-client-secret",
        auth_state_secret="state-secret",
        jwt_access_secret="jwt-access-secret-jwt-access-secret-123",
        jwt_refresh_secret="jwt-refresh-secret-jwt-refresh-secret-123",
        jwt_issuer="volley-erp",
        jwt_audience="volley-erp-client",
        jwt_access_ttl_seconds=600,
        jwt_refresh_ttl_seconds=604800,
        auth_redirect_allowed_origins=["https://app.example.com"],
        auth_redirect_allowed_schemes=["myapp"],
        auth_mobile_allowed_platforms=["android", "ios"],
        auth_mobile_redirect_allowed_android=["com.example.android:/oauth2redirect"],
        auth_mobile_redirect_allowed_ios=["com.example.ios:/oauth2redirect"],
        token_enc_key="test-token-encryption-key",
        token_enc_key_secret_name=None,
        invite_token_ttl_seconds=604800,
        app_public_base_url="https://app.example.com",
    )


class FakeOrganizationRepository:
    def __init__(self) -> None:
        self.org = {
            "org_id": "org-1",
            "name": "Org One",
            "owner_user_id": "user-1",
            "storage_owner_user_id": "user-1",
            "workspace_root_folder_id": None,
            "workspace_sheets_folder_id": None,
            "workspace_images_folder_id": None,
            "workspace_exports_folder_id": None,
        }
        self.updated = None

    def get_organization(self, *, org_id: str):
        if org_id != self.org["org_id"]:
            return None
        return dict(self.org)

    def update_organization_workspace_ids(
        self,
        *,
        org_id: str,
        workspace_root_folder_id: str,
        workspace_sheets_folder_id: str,
        workspace_images_folder_id: str,
        workspace_exports_folder_id: str,
    ):
        self.org["workspace_root_folder_id"] = workspace_root_folder_id
        self.org["workspace_sheets_folder_id"] = workspace_sheets_folder_id
        self.org["workspace_images_folder_id"] = workspace_images_folder_id
        self.org["workspace_exports_folder_id"] = workspace_exports_folder_id
        self.updated = dict(self.org)
        return dict(self.org)


class FakeGoogleConnectionRepository:
    def __init__(self, encrypted_refresh_token: str | None):
        self.connection = (
            {
                "provider": "google",
                "encrypted_refresh_token": encrypted_refresh_token,
            }
            if encrypted_refresh_token
            else None
        )

    def get_by_user_id(self, *, user_id: str):
        return dict(self.connection) if self.connection else None


class FakeGoogleDriveRepository:
    def __init__(self) -> None:
        self.raise_error = False
        self.created_count = 0
        self.ensure_calls = []
        self.folders = {}

    def build_user_drive_service(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ):
        if self.raise_error:
            raise GoogleDriveRepositoryError("Google Drive API is not enabled.")
        return "drive"

    def get_folder_by_id(self, *, drive_service, folder_id: str):
        return self.folders.get(folder_id)

    def ensure_folder(
        self,
        *,
        drive_service,
        folder_name: str,
        app_properties: dict[str, str],
        parent_folder_id: str | None = None,
        fallback_to_name_search: bool = True,
    ):
        del fallback_to_name_search
        if self.raise_error:
            raise GoogleDriveRepositoryError("Google Drive API is not enabled.")
        self.ensure_calls.append((folder_name, parent_folder_id, dict(app_properties)))
        for folder in self.folders.values():
            if (
                folder["name"] == folder_name
                and folder["parents"] == ([parent_folder_id] if parent_folder_id else [])
                and folder["appProperties"] == app_properties
            ):
                return dict(folder)

        folder_id = f"folder-{len(self.folders) + 1}"
        folder = {
            "id": folder_id,
            "name": folder_name,
            "parents": [parent_folder_id] if parent_folder_id else [],
            "appProperties": dict(app_properties),
        }
        self.folders[folder_id] = folder
        self.created_count += 1
        return dict(folder)


class WorkspaceServiceTestCase(unittest.TestCase):
    def _build_service(self):
        auth_config = _build_auth_config()
        encryption = RefreshTokenEncryptionService(auth_config=auth_config)
        refresh_token_enc = encryption.encrypt("google-refresh-token")
        org_repo = FakeOrganizationRepository()
        connection_repo = FakeGoogleConnectionRepository(refresh_token_enc)
        drive_repo = FakeGoogleDriveRepository()
        service = WorkspaceService(
            auth_config=auth_config,
            organization_repository=org_repo,
            google_connection_repository=connection_repo,
            google_drive_repository=drive_repo,
            refresh_token_encryption_service=encryption,
        )
        return service, org_repo, drive_repo

    def test_missing_workspace_creates_folders_and_persists_ids(self):
        service, org_repo, drive_repo = self._build_service()
        workspace = service.ensure_workspace_for_organization(org_id="org-1")

        self.assertEqual(workspace["workspace_root_folder_id"], "folder-3")
        self.assertEqual(workspace["workspace_sheets_folder_id"], "folder-4")
        self.assertEqual(workspace["workspace_images_folder_id"], "folder-5")
        self.assertEqual(workspace["workspace_exports_folder_id"], "folder-6")
        self.assertIsNotNone(org_repo.updated)
        self.assertEqual(drive_repo.created_count, 6)

    def test_existing_persisted_workspace_reuses_subfolders(self):
        service, org_repo, drive_repo = self._build_service()
        org_repo.org.update(
            {
                "workspace_root_folder_id": "org-root",
                "workspace_sheets_folder_id": "org-sheets",
                "workspace_images_folder_id": "org-images",
                "workspace_exports_folder_id": "org-exports",
            }
        )
        drive_repo.folders.update(
            {
                "app-root": {
                    "id": "app-root",
                    "name": "Volley ERP",
                    "parents": ["root"],
                    "appProperties": {
                        "app": "volley_erp",
                        "type": "workspace_root",
                    },
                },
                "orgs-container": {
                    "id": "orgs-container",
                    "name": "organizations",
                    "parents": ["app-root"],
                    "appProperties": {
                        "app": "volley_erp",
                        "type": "workspace_organizations_container",
                    },
                },
                "org-root": {
                    "id": "org-root",
                    "name": "org-1 - Org One",
                    "parents": ["orgs-container"],
                    "appProperties": {
                        "app": "volley_erp",
                        "type": "organization_root",
                        "org_id": "org-1",
                    },
                },
                "org-sheets": {
                    "id": "org-sheets",
                    "name": "sheets",
                    "parents": ["org-root"],
                    "appProperties": {
                        "app": "volley_erp",
                        "type": "organization_subfolder",
                        "org_id": "org-1",
                        "subfolder": "sheets",
                    },
                },
                "org-images": {
                    "id": "org-images",
                    "name": "images",
                    "parents": ["org-root"],
                    "appProperties": {
                        "app": "volley_erp",
                        "type": "organization_subfolder",
                        "org_id": "org-1",
                        "subfolder": "images",
                    },
                },
                "org-exports": {
                    "id": "org-exports",
                    "name": "exports",
                    "parents": ["org-root"],
                    "appProperties": {
                        "app": "volley_erp",
                        "type": "organization_subfolder",
                        "org_id": "org-1",
                        "subfolder": "exports",
                    },
                },
            }
        )
        workspace = service.ensure_workspace_for_organization(org_id="org-1")

        self.assertEqual(workspace["workspace_root_folder_id"], "org-root")
        self.assertEqual(workspace["workspace_sheets_folder_id"], "org-sheets")
        self.assertEqual(workspace["workspace_images_folder_id"], "org-images")
        self.assertEqual(workspace["workspace_exports_folder_id"], "org-exports")

    def test_missing_storage_owner_connection_raises_specific_error(self):
        auth_config = _build_auth_config()
        encryption = RefreshTokenEncryptionService(auth_config=auth_config)
        org_repo = FakeOrganizationRepository()
        connection_repo = FakeGoogleConnectionRepository(None)
        drive_repo = FakeGoogleDriveRepository()
        service = WorkspaceService(
            auth_config=auth_config,
            organization_repository=org_repo,
            google_connection_repository=connection_repo,
            google_drive_repository=drive_repo,
            refresh_token_encryption_service=encryption,
        )
        with self.assertRaises(StorageOwnerConnectionMissingError):
            service.ensure_workspace_for_organization(org_id="org-1")

    def test_drive_error_raises_clean_workspace_provisioning_error(self):
        service, _, drive_repo = self._build_service()
        drive_repo.raise_error = True
        with self.assertRaises(WorkspaceProvisioningFailedError):
            service.ensure_workspace_for_organization(org_id="org-1")


if __name__ == "__main__":
    unittest.main()

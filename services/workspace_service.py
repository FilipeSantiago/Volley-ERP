import logging
from typing import Any

from repositories.google_connection_repository import (
    GoogleConnectionRepository,
    GoogleConnectionRepositoryError,
)
from repositories.google_drive_repository import (
    GoogleDriveRepository,
    GoogleDriveRepositoryError,
)
from repositories.organization_repository import (
    OrganizationRepository,
    OrganizationRepositoryError,
)
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import (
    OrganizationNotFoundError,
    StorageOwnerConnectionMissingError,
    WorkspaceProvisioningFailedError,
)
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)

logger = logging.getLogger(__name__)

WORKSPACE_ROOT_NAME = "Volley ERP"
ORGANIZATIONS_FOLDER_NAME = "organizations"
APP_MARKER = "volley_erp"


class WorkspaceService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        organization_repository: OrganizationRepository,
        google_connection_repository: GoogleConnectionRepository,
        google_drive_repository: GoogleDriveRepository,
        refresh_token_encryption_service: RefreshTokenEncryptionService,
    ) -> None:
        self._auth_config = auth_config
        self._organization_repository = organization_repository
        self._google_connection_repository = google_connection_repository
        self._google_drive_repository = google_drive_repository
        self._refresh_token_encryption_service = refresh_token_encryption_service

    def provision_workspace_for_new_organization(
        self, *, org_id: str, storage_owner_user_id: str
    ) -> dict[str, str]:
        return self.ensure_workspace_for_organization(
            org_id=org_id,
            expected_storage_owner_user_id=storage_owner_user_id,
        )

    def ensure_workspace_for_organization(
        self,
        *,
        org_id: str,
        expected_storage_owner_user_id: str | None = None,
    ) -> dict[str, str]:
        organization = self._get_organization(org_id=org_id)
        storage_owner_user_id = organization["storage_owner_user_id"]
        if expected_storage_owner_user_id and (
            storage_owner_user_id != expected_storage_owner_user_id
        ):
            raise WorkspaceProvisioningFailedError(
                "Organization storage owner does not match expected user."
            )

        refresh_token = self._load_storage_owner_refresh_token(
            user_id=storage_owner_user_id
        )
        try:
            drive_service = self._google_drive_repository.build_user_drive_service(
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
            )

            workspace_root = self._ensure_workspace_root(drive_service=drive_service)
            organizations_folder = self._ensure_organizations_container(
                drive_service=drive_service,
                workspace_root_id=workspace_root["id"],
            )
            organization_root = self._ensure_organization_folder(
                drive_service=drive_service,
                org_id=org_id,
                org_name=organization["name"],
                parent_folder_id=organizations_folder["id"],
                persisted_folder_id=self._optional_str(
                    organization.get("workspace_root_folder_id")
                ),
            )
            sheets_folder = self._ensure_org_subfolder(
                drive_service=drive_service,
                org_id=org_id,
                org_root_id=organization_root["id"],
                persisted_folder_id=self._optional_str(
                    organization.get("workspace_sheets_folder_id")
                ),
                name="sheets",
            )
            images_folder = self._ensure_org_subfolder(
                drive_service=drive_service,
                org_id=org_id,
                org_root_id=organization_root["id"],
                persisted_folder_id=self._optional_str(
                    organization.get("workspace_images_folder_id")
                ),
                name="images",
            )
            exports_folder = self._ensure_org_subfolder(
                drive_service=drive_service,
                org_id=org_id,
                org_root_id=organization_root["id"],
                persisted_folder_id=self._optional_str(
                    organization.get("workspace_exports_folder_id")
                ),
                name="exports",
            )
        except GoogleDriveRepositoryError as error:
            logger.warning(
                "Failed to ensure organization workspace org_id=%s: %s",
                org_id,
                error,
            )
            raise WorkspaceProvisioningFailedError(
                str(error)
            ) from error

        workspace = {
            "workspace_root_folder_id": organization_root["id"],
            "workspace_sheets_folder_id": sheets_folder["id"],
            "workspace_images_folder_id": images_folder["id"],
            "workspace_exports_folder_id": exports_folder["id"],
        }

        try:
            self._organization_repository.update_organization_workspace_ids(
                org_id=org_id,
                workspace_root_folder_id=workspace["workspace_root_folder_id"],
                workspace_sheets_folder_id=workspace["workspace_sheets_folder_id"],
                workspace_images_folder_id=workspace["workspace_images_folder_id"],
                workspace_exports_folder_id=workspace["workspace_exports_folder_id"],
            )
        except OrganizationRepositoryError as error:
            raise WorkspaceProvisioningFailedError(
                "Failed to persist organization workspace IDs."
            ) from error

        return workspace

    def _ensure_workspace_root(self, *, drive_service: Any) -> dict[str, Any]:
        return self._google_drive_repository.ensure_folder(
            drive_service=drive_service,
            folder_name=WORKSPACE_ROOT_NAME,
            parent_folder_id="root",
            app_properties={"app": APP_MARKER, "type": "workspace_root"},
        )

    def _ensure_organizations_container(
        self, *, drive_service: Any, workspace_root_id: str
    ) -> dict[str, Any]:
        return self._google_drive_repository.ensure_folder(
            drive_service=drive_service,
            folder_name=ORGANIZATIONS_FOLDER_NAME,
            parent_folder_id=workspace_root_id,
            app_properties={
                "app": APP_MARKER,
                "type": "workspace_organizations_container",
            },
        )

    def _ensure_organization_folder(
        self,
        *,
        drive_service: Any,
        org_id: str,
        org_name: str,
        parent_folder_id: str,
        persisted_folder_id: str | None,
    ) -> dict[str, Any]:
        expected_properties = {
            "app": APP_MARKER,
            "type": "organization_root",
            "org_id": org_id,
        }
        expected_name = f"{org_id} - {org_name}"

        if persisted_folder_id:
            persisted = self._google_drive_repository.get_folder_by_id(
                drive_service=drive_service,
                folder_id=persisted_folder_id,
            )
            if persisted and self._matches_folder(
                folder=persisted,
                expected_parent_id=parent_folder_id,
                expected_properties=expected_properties,
            ):
                return persisted

        return self._google_drive_repository.ensure_folder(
            drive_service=drive_service,
            folder_name=expected_name,
            parent_folder_id=parent_folder_id,
            app_properties=expected_properties,
        )

    def _ensure_org_subfolder(
        self,
        *,
        drive_service: Any,
        org_id: str,
        org_root_id: str,
        persisted_folder_id: str | None,
        name: str,
    ) -> dict[str, Any]:
        expected_properties = {
            "app": APP_MARKER,
            "type": "organization_subfolder",
            "org_id": org_id,
            "subfolder": name,
        }
        if persisted_folder_id:
            persisted = self._google_drive_repository.get_folder_by_id(
                drive_service=drive_service,
                folder_id=persisted_folder_id,
            )
            if persisted and self._matches_folder(
                folder=persisted,
                expected_parent_id=org_root_id,
                expected_properties=expected_properties,
            ):
                return persisted

        return self._google_drive_repository.ensure_folder(
            drive_service=drive_service,
            folder_name=name,
            parent_folder_id=org_root_id,
            app_properties=expected_properties,
        )

    def _load_storage_owner_refresh_token(self, *, user_id: str) -> str:
        try:
            connection = self._google_connection_repository.get_by_user_id(user_id=user_id)
        except GoogleConnectionRepositoryError as error:
            raise StorageOwnerConnectionMissingError(
                "storage_owner_connection_missing"
            ) from error

        if connection is None:
            raise StorageOwnerConnectionMissingError("storage_owner_connection_missing")

        encrypted_refresh_token = connection.get("encrypted_refresh_token")
        if not isinstance(encrypted_refresh_token, str) or not encrypted_refresh_token:
            raise StorageOwnerConnectionMissingError("storage_owner_connection_missing")

        return self._refresh_token_encryption_service.decrypt(encrypted_refresh_token)

    def _get_organization(self, *, org_id: str) -> dict[str, Any]:
        try:
            organization = self._organization_repository.get_organization(org_id=org_id)
        except OrganizationRepositoryError as error:
            raise OrganizationNotFoundError("organization_not_found") from error

        if organization is None:
            raise OrganizationNotFoundError("organization_not_found")
        return organization

    @staticmethod
    def _matches_folder(
        *,
        folder: dict[str, Any],
        expected_parent_id: str,
        expected_properties: dict[str, str],
    ) -> bool:
        parents = folder.get("parents") or []
        if expected_parent_id not in parents:
            return False
        properties = folder.get("appProperties") or {}
        if not isinstance(properties, dict):
            return False
        for key, value in expected_properties.items():
            if properties.get(key) != value:
                return False
        return True

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        return None

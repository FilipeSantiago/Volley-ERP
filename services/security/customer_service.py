from repositories.customer_repository import CustomerRepository, CustomerRepositoryError
from repositories.workspace_repository import WorkspaceRepository, WorkspaceRepositoryError
from services.security.auth_config import AuthConfig
from services.security.auth_exceptions import (
    CustomerNotFoundError,
    WorkspaceCreationError,
)
from services.security.jwt_token_service import JWTTokenService
from services.security.refresh_token_encryption_service import (
    RefreshTokenEncryptionService,
)


class CustomerService:
    def __init__(
        self,
        *,
        auth_config: AuthConfig,
        customer_repository: CustomerRepository,
        workspace_repository: WorkspaceRepository,
        token_service: JWTTokenService,
        refresh_token_encryption_service: RefreshTokenEncryptionService,
    ) -> None:
        self._auth_config = auth_config
        self._customer_repository = customer_repository
        self._workspace_repository = workspace_repository
        self._token_service = token_service
        self._refresh_token_encryption_service = refresh_token_encryption_service

    def create_workspace(
        self, *, customer_id: str, workspace_name: str | None
    ) -> dict[str, str | int | None]:
        customer = self._customer_repository.get_by_customer_id(customer_id=customer_id)
        if customer is None:
            raise CustomerNotFoundError("Customer not found.")

        refresh_token_enc = customer.get("refresh_token_enc")
        if not isinstance(refresh_token_enc, str) or not refresh_token_enc:
            raise WorkspaceCreationError("Customer does not have a refresh token.")

        refresh_token = self._refresh_token_encryption_service.decrypt(refresh_token_enc)
        resolved_workspace_name = (
            workspace_name.strip()
            if isinstance(workspace_name, str) and workspace_name.strip()
            else "Volley ERP Workspace"
        )

        try:
            workspace = self._workspace_repository.create_workspace(
                refresh_token=refresh_token,
                client_id=self._auth_config.google_oauth_client_id,
                client_secret=self._auth_config.google_oauth_client_secret,
                workspace_name=resolved_workspace_name,
            )
        except WorkspaceRepositoryError as error:
            raise WorkspaceCreationError("Failed to create customer workspace.") from error

        doc_id = workspace.get("doc_id")
        if isinstance(doc_id, str):
            try:
                customer = self._customer_repository.update_doc_id(
                    customer_id=customer_id,
                    doc_id=doc_id,
                )
            except CustomerRepositoryError as error:
                raise WorkspaceCreationError("Failed to update customer workspace.") from error

        token_pair = self._token_service.issue_token_pair(customer)
        return {
            "status": "ok",
            "customer_id": customer["customer_id"],
            "doc_id": customer.get("doc_id"),
            "workspace_folder_id": workspace.get("workspace_folder_id"),
            "workspace_folder_link": workspace.get("workspace_folder_link"),
            "doc_link": workspace.get("doc_link"),
            **token_pair,
        }

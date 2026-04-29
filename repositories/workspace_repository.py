from repositories.helpers.google_workspace_helper import (
    GoogleWorkspaceHelper,
    GoogleWorkspaceHelperError,
)


class WorkspaceRepositoryError(Exception):
    pass


class WorkspaceRepository:
    def __init__(self, *, workspace_helper: GoogleWorkspaceHelper) -> None:
        self._workspace_helper = workspace_helper

    def create_workspace(
        self,
        *,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        workspace_name: str,
    ) -> dict[str, str | None]:
        try:
            return self._workspace_helper.create_workspace(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
                workspace_name=workspace_name,
            )
        except GoogleWorkspaceHelperError as error:
            raise WorkspaceRepositoryError(
                "Failed to create workspace in Google APIs."
            ) from error

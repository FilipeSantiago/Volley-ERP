from repositories.helpers.google_drive_folders_helper import (
    GoogleDriveFoldersHelper,
    GoogleDriveHelperError,
)


class TeamRepositoryError(Exception):
    pass


class TeamRepository:
    def __init__(self, *, drive_folders_helper: GoogleDriveFoldersHelper) -> None:
        self._drive_folders_helper = drive_folders_helper

    def find_team_folder(
        self, *, team_name: str, root_folder_id: str
    ) -> dict[str, str | None] | None:
        try:
            return self._drive_folders_helper.find_folder_by_name(
                folder_name=team_name,
                parent_folder_id=root_folder_id,
            )
        except GoogleDriveHelperError as error:
            raise TeamRepositoryError(
                "Failed to search team folders in Google Drive."
            ) from error

    def list_team_folders(
        self, *, root_folder_id: str
    ) -> list[dict[str, str | None]]:
        try:
            return self._drive_folders_helper.list_folders(
                parent_folder_id=root_folder_id
            )
        except GoogleDriveHelperError as error:
            raise TeamRepositoryError(
                "Failed to list team folders in Google Drive."
            ) from error

    def create_team_structure(
        self, *, team_name: str, root_folder_id: str
    ) -> dict[str, dict[str, str | None]]:
        try:
            team_folder = self._drive_folders_helper.create_folder(
                folder_name=team_name,
                parent_folder_id=root_folder_id,
            )
            photos_folder = self._drive_folders_helper.create_folder(
                folder_name="photos",
                parent_folder_id=team_folder["id"],
            )
        except GoogleDriveHelperError as error:
            raise TeamRepositoryError(
                "Failed to create team folders in Google Drive."
            ) from error

        return {"team_folder": team_folder, "photos_folder": photos_folder}

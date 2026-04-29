from typing import Any

from repositories.team_repository import TeamRepository, TeamRepositoryError
from services.exceptions import (
    InvalidTeamNameError,
    RootFolderNotConfiguredError,
    TeamAlreadyExistsError,
    TeamCreationError,
)


class TeamService:
    def __init__(
        self, *, team_repository: TeamRepository, root_folder_id: str | None
    ) -> None:
        self._team_repository = team_repository
        self._root_folder_id = root_folder_id

    def create_team(self, team_name: Any) -> dict[str, str | None]:
        normalized_team_name = self._normalize_team_name(team_name)
        root_folder_id = self._get_root_folder_id()

        existing_team = self._team_repository.find_team_folder(
            team_name=normalized_team_name,
            root_folder_id=root_folder_id,
        )
        if existing_team is not None:
            raise TeamAlreadyExistsError(
                team_name=normalized_team_name,
                team_folder_id=existing_team["id"],
            )

        try:
            folder_structure = self._team_repository.create_team_structure(
                team_name=normalized_team_name,
                root_folder_id=root_folder_id,
            )
        except TeamRepositoryError as error:
            raise TeamCreationError(
                "Could not create team structure in Google Drive."
            ) from error

        team_folder = folder_structure["team_folder"]
        photos_folder = folder_structure["photos_folder"]

        return {
            "team_name": normalized_team_name,
            "team_folder_id": team_folder["id"],
            "photos_folder_id": photos_folder["id"],
            "team_folder_link": team_folder.get("webViewLink"),
        }

    def list_teams(self) -> dict[str, Any]:
        root_folder_id = self._get_root_folder_id()
        try:
            team_folders = self._team_repository.list_team_folders(
                root_folder_id=root_folder_id
            )
        except TeamRepositoryError as error:
            raise TeamCreationError(
                "Could not list teams in Google Drive."
            ) from error

        items = [
            {
                "team_name": team_folder["name"],
                "team_folder_id": team_folder["id"],
                "team_folder_link": team_folder.get("webViewLink"),
            }
            for team_folder in team_folders
        ]
        return {"items": items, "count": len(items)}

    @staticmethod
    def _normalize_team_name(team_name: Any) -> str:
        if not isinstance(team_name, str):
            raise InvalidTeamNameError("team_name must be a non-empty string.")

        normalized_team_name = team_name.strip()
        if not normalized_team_name:
            raise InvalidTeamNameError("team_name must be a non-empty string.")

        return normalized_team_name

    def _get_root_folder_id(self) -> str:
        if not self._root_folder_id:
            raise RootFolderNotConfiguredError(
                "Customer root folder is not configured. Set CUSTOMER_ROOT_FOLDER_ID."
            )

        return self._root_folder_id

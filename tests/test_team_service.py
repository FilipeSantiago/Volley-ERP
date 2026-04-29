import unittest

from repositories.team_repository import TeamRepositoryError
from services.exceptions import (
    InvalidTeamNameError,
    RootFolderNotConfiguredError,
    TeamAlreadyExistsError,
    TeamCreationError,
)
from services.team_service import TeamService


class FakeTeamRepository:
    def __init__(self) -> None:
        self.created = []
        self.listed = []
        self.existing_folder = None
        self.list_result = []
        self.raise_on_create = False
        self.raise_on_list = False

    def find_team_folder(self, *, team_name: str, root_folder_id: str):
        return self.existing_folder

    def list_team_folders(self, *, root_folder_id: str):
        if self.raise_on_list:
            raise TeamRepositoryError("drive error")
        self.listed.append(root_folder_id)
        return list(self.list_result)

    def create_team_structure(self, *, team_name: str, root_folder_id: str):
        if self.raise_on_create:
            raise TeamRepositoryError("drive error")

        team_folder_id = f"{team_name}-id"
        photos_folder_id = "photos-id"
        self.created.append((team_name, root_folder_id))
        self.created.append(("photos", team_folder_id))
        return {
            "team_folder": {
                "id": team_folder_id,
                "name": team_name,
                "webViewLink": f"link://{team_folder_id}",
            },
            "photos_folder": {
                "id": photos_folder_id,
                "name": "photos",
                "webViewLink": f"link://{photos_folder_id}",
            },
        }


class TeamServiceTestCase(unittest.TestCase):
    def test_list_teams_returns_items_and_count(self):
        team_repository = FakeTeamRepository()
        team_repository.list_result = [
            {"id": "team-a-id", "name": "Team A", "webViewLink": "link://team-a-id"},
            {"id": "team-b-id", "name": "Team B", "webViewLink": "link://team-b-id"},
        ]
        service = TeamService(
            team_repository=team_repository,
            root_folder_id="root-folder-id",
        )

        result = service.list_teams()

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["items"][0]["team_name"], "Team A")
        self.assertEqual(result["items"][0]["team_folder_id"], "team-a-id")
        self.assertEqual(result["items"][0]["team_folder_link"], "link://team-a-id")
        self.assertEqual(result["items"][1]["team_name"], "Team B")
        self.assertEqual(team_repository.listed, ["root-folder-id"])

    def test_list_teams_requires_configured_root_folder(self):
        team_repository = FakeTeamRepository()
        service = TeamService(
            team_repository=team_repository,
            root_folder_id=None,
        )

        with self.assertRaises(RootFolderNotConfiguredError):
            service.list_teams()

    def test_list_teams_raises_creation_error_on_drive_failure(self):
        team_repository = FakeTeamRepository()
        team_repository.raise_on_list = True
        service = TeamService(
            team_repository=team_repository,
            root_folder_id="root-folder-id",
        )

        with self.assertRaises(TeamCreationError):
            service.list_teams()

    def test_create_team_creates_team_and_photos_folders(self):
        team_repository = FakeTeamRepository()
        service = TeamService(
            team_repository=team_repository,
            root_folder_id="root-folder-id",
        )

        result = service.create_team("Team A")

        self.assertEqual(result["team_name"], "Team A")
        self.assertEqual(result["team_folder_id"], "Team A-id")
        self.assertEqual(result["photos_folder_id"], "photos-id")
        self.assertEqual(result["team_folder_link"], "link://Team A-id")
        self.assertEqual(
            team_repository.created,
            [("Team A", "root-folder-id"), ("photos", "Team A-id")],
        )

    def test_create_team_requires_non_empty_string_name(self):
        team_repository = FakeTeamRepository()
        service = TeamService(
            team_repository=team_repository,
            root_folder_id="root-folder-id",
        )

        with self.assertRaises(InvalidTeamNameError):
            service.create_team("   ")

        with self.assertRaises(InvalidTeamNameError):
            service.create_team(None)

    def test_create_team_requires_configured_root_folder(self):
        team_repository = FakeTeamRepository()
        service = TeamService(
            team_repository=team_repository,
            root_folder_id=None,
        )

        with self.assertRaises(RootFolderNotConfiguredError):
            service.create_team("Team A")

    def test_create_team_rejects_duplicate_team_name(self):
        team_repository = FakeTeamRepository()
        team_repository.existing_folder = {
            "id": "existing-team-id",
            "name": "Team A",
            "webViewLink": "link://existing-team-id",
        }
        service = TeamService(
            team_repository=team_repository,
            root_folder_id="root-folder-id",
        )

        with self.assertRaises(TeamAlreadyExistsError):
            service.create_team("Team A")

    def test_create_team_raises_creation_error_on_drive_failure(self):
        team_repository = FakeTeamRepository()
        team_repository.raise_on_create = True
        service = TeamService(
            team_repository=team_repository,
            root_folder_id="root-folder-id",
        )

        with self.assertRaises(TeamCreationError):
            service.create_team("Team A")


if __name__ == "__main__":
    unittest.main()

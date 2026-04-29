from dataclasses import dataclass

from repositories.athlete_repository import AthleteRepository
from repositories.helpers.google_drive_folders_helper import GoogleDriveFoldersHelper
from repositories.helpers.google_sheets_helper import GoogleSheetsHelper
from repositories.team_repository import TeamRepository
from services.athlete_service import AthleteService
from services.team_service import TeamService


@dataclass(frozen=True)
class DomainServicesContainer:
    team_service: TeamService
    athlete_service: AthleteService


def build_domain_services_container(
    *, root_folder_id: str | None
) -> DomainServicesContainer:
    drive_folders_helper = GoogleDriveFoldersHelper()
    sheets_helper = GoogleSheetsHelper()

    team_repository = TeamRepository(drive_folders_helper=drive_folders_helper)
    athlete_repository = AthleteRepository(
        drive_folders_helper=drive_folders_helper,
        sheets_helper=sheets_helper,
    )

    team_service = TeamService(
        team_repository=team_repository,
        root_folder_id=root_folder_id,
    )
    athlete_service = AthleteService(athlete_repository=athlete_repository)

    return DomainServicesContainer(
        team_service=team_service,
        athlete_service=athlete_service,
    )

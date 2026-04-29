class TeamServiceError(Exception):
    pass


class InvalidTeamNameError(TeamServiceError):
    pass


class RootFolderNotConfiguredError(TeamServiceError):
    pass


class TeamAlreadyExistsError(TeamServiceError):
    def __init__(self, team_name: str, team_folder_id: str) -> None:
        self.team_name = team_name
        self.team_folder_id = team_folder_id
        super().__init__(f"Team '{team_name}' already exists.")


class TeamCreationError(TeamServiceError):
    pass


class AthleteServiceError(Exception):
    pass


class InvalidAthletePayloadError(AthleteServiceError):
    pass


class TeamFolderNotFoundError(AthleteServiceError):
    pass


class AthleteCreationError(AthleteServiceError):
    pass

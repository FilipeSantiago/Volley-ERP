from pydantic import BaseModel, Field


class CreateTeamRequest(BaseModel):
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str | None = None
    gender: str | None = None


class TeamQuery(BaseModel):
    org_id: str = Field(min_length=1)


class TeamDetailQuery(BaseModel):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class TeamMemberCreateRequest(BaseModel):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    email: str = Field(min_length=1)
    team_role: str = Field(min_length=1)


class Team(BaseModel):
    team_id: str
    name: str | None = None
    category: str | None = None
    gender: str | None = None
    status: str | None = None
    team_role: str | None = None
    team_spreadsheet_id: str | None = None
    team_spreadsheet_url: str | None = None


class TeamListResponse(BaseModel):
    items: list[Team]
    count: int


class TeamMemberRecord(BaseModel):
    user_id: str | None = None
    email: str | None = None
    team_role: str | None = None
    status: str | None = None


class TeamMembersResponse(BaseModel):
    items: list[TeamMemberRecord]
    count: int


class TeamMemberMutationResponse(BaseModel):
    status: str
    team_id: str | None = None
    user_id: str | None = None
    team_role: str | None = None
    invite_id: str | None = None
    invite_url: str | None = None
    expires_at: str | None = None

from pydantic import BaseModel, Field


class OrganizationTeam(BaseModel):
    team_id: str | None = None
    name: str | None = None
    team_role: str | None = None
    status: str | None = None


class Organization(BaseModel):
    org_id: str
    name: str | None = None
    org_role: str | None = None
    status: str | None = None
    can_access_all_teams: bool | None = None
    teams: list[OrganizationTeam] = Field(default_factory=list)


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1)


class CreateOrganizationResponse(BaseModel):
    org_id: str
    name: str
    org_role: str
    workspace_status: str
    workspace_root_folder_id: str | None = None
    workspace_sheets_folder_id: str | None = None
    workspace_images_folder_id: str | None = None
    workspace_exports_folder_id: str | None = None


class OrganizationListResponse(BaseModel):
    items: list[Organization]
    count: int

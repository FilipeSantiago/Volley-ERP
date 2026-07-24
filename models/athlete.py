from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from models.enums import AthletePosition, AthleteSize


class Athlete(BaseModel):
    athlete_id: str
    full_name: str
    birthday: date
    cpf: str
    cellphone: str
    tshirt_size: AthleteSize | None = None
    shorts_size: AthleteSize | None = None
    position: AthletePosition | None = None
    rg: str | None = None
    email: str | None = None
    photo_link: str | None = None
    org_id: str | None = None
    team_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("birthday", mode="before")
    @classmethod
    def parse_birthday(cls, value: Any) -> Any:
        return _parse_date_value(value)


class AthleteWriteFields(BaseModel):
    full_name: str = Field(min_length=1)
    birthday: date
    cpf: str = Field(min_length=1)
    cellphone: str = Field(min_length=1)
    tshirt_size: AthleteSize | None = None
    shorts_size: AthleteSize | None = None
    position: AthletePosition
    rg: str | None = None
    email: str | None = None

    @field_validator("birthday", mode="before")
    @classmethod
    def parse_birthday(cls, value: Any) -> Any:
        return _parse_date_value(value)


class AthleteCreateRequest(AthleteWriteFields):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class AthleteUpdateRequest(AthleteWriteFields):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    athlete_id: str = Field(min_length=1)


class AthleteListQuery(BaseModel):
    org_id: str = Field(min_length=1)
    team_id: str | None = Field(default=None, min_length=1)


class AthleteListResponse(BaseModel):
    org_id: str
    team_id: str | None = None
    athletes_sheet_id: str | None = None
    athletes_sheet_url: str | None = None
    items: list[Athlete]
    count: int


class AthleteWriteResponse(AthleteWriteFields):
    org_id: str
    team_id: str
    athletes_sheet_id: str
    athletes_sheet_url: str | None = None
    athlete_id: str
    photo_link: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class AthletePhotoResponse(BaseModel):
    athlete_id: str
    photo_link: str | None = None
    full_name: str | None = None
    org_id: str | None = None
    team_id: str | None = None


def _parse_date_value(value: Any) -> Any:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return value
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(cleaned, fmt).date()
            except ValueError:
                continue
        return value
    return value

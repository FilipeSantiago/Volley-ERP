from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from models.entity.person import PersonFields
from models.enums import AthletePosition, AthleteSize


class Athlete(PersonFields):
    athlete_id: str = Field(default_factory=lambda: str(uuid4()))
    person_id: str | None = None
    position: AthletePosition
    org_id: str | None = None
    team_id: str | None = None
    photo_link: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("birthday", mode="before")
    @classmethod
    def parse_birthday(cls, value: Any) -> Any:
        return _parse_date_value(value)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)


class AthleteWriteFields(BaseModel):
    full_name: str = Field(min_length=1)
    birthday: date
    cpf: str = Field(min_length=1)
    cellphone: str = Field(min_length=1)
    position: AthletePosition
    tshirt_size: AthleteSize | None = None
    shorts_size: AthleteSize | None = None
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


def _ensure_aware_datetime(value: Any) -> Any:
    if value is None or not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

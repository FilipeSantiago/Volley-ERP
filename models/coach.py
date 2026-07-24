from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from models.enums import AthletePosition, AthleteSize


class CoachWriteFields(BaseModel):
    full_name: str = Field(min_length=1)
    birthday: date
    cpf: str = Field(min_length=1)
    cellphone: str = Field(min_length=1)
    tshirt_size: AthleteSize | None = None
    shorts_size: AthleteSize | None = None
    position: AthletePosition
    rg: str | None = None
    email: str | None = None
    pix_key: str = Field(min_length=1)

    @field_validator("birthday", mode="before")
    @classmethod
    def parse_birthday(cls, value: Any) -> Any:
        return _parse_date_value(value)


class CoachCreateRequest(CoachWriteFields):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class CoachUpdateRequest(CoachWriteFields):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class CoachQuery(BaseModel):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class CoachResponse(CoachWriteFields):
    org_id: str
    team_id: str
    coach_sheet_id: str
    coach_sheet_url: str | None = None
    photo_link: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


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

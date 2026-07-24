from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, Field, field_validator

from models.entity.person import PersonFields, _parse_date_value
from models.enums import AthletePosition, AthleteSize

_BR_CENTS = Decimal("0.01")


class Coach(PersonFields):
    person_id: str | None = None
    org_id: str | None = None
    team_id: str
    position: AthletePosition
    pix_key: str = Field(min_length=1)
    training_fee: Decimal = Field(default=Decimal("0.00"))
    game_fee: Decimal = Field(default=Decimal("0.00"))
    photo_link: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    coach_sheet_id: str | None = None
    coach_sheet_url: str | None = None

    @field_validator("birthday", mode="before")
    @classmethod
    def parse_birthday(cls, value: Any) -> Any:
        return _parse_date_value(value)

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)

    @field_validator("training_fee", "game_fee", mode="before")
    @classmethod
    def normalize_fee(cls, value: Any) -> Decimal:
        return _normalize_money(value, minimum=Decimal("0.00"))


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
    training_fee: Decimal = Field(default=Decimal("0.00"))
    game_fee: Decimal = Field(default=Decimal("0.00"))

    @field_validator("training_fee", "game_fee", mode="before")
    @classmethod
    def normalize_fee(cls, value: Any) -> Decimal:
        return _normalize_money(value, minimum=Decimal("0.00"))


def _normalize_money(value: Any, *, minimum: Decimal) -> Decimal:
    if isinstance(value, Decimal):
        normalized = value
    elif value is None or value == "":
        normalized = Decimal("0.00")
    else:
        normalized = Decimal(str(value).replace(",", "."))
    normalized = normalized.quantize(_BR_CENTS, rounding=ROUND_HALF_UP)
    if normalized < minimum:
        raise ValueError(f"amount must be greater than or equal to {minimum}.")
    return normalized


def _ensure_aware_datetime(value: Any) -> Any:
    if value is None or not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

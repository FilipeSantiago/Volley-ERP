from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from models.enums import AthleteSize


class PersonFields(BaseModel):
    full_name: str = Field(min_length=1)
    birthday: date
    cpf: str = Field(min_length=1)
    cellphone: str = Field(min_length=1)
    tshirt_size: AthleteSize | None = None
    shorts_size: AthleteSize | None = None
    rg: str | None = None
    email: str | None = None

    @field_validator("birthday", mode="before")
    @classmethod
    def parse_birthday(cls, value: Any) -> Any:
        return _parse_date_value(value)


class Person(PersonFields):
    person_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str | None = None


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

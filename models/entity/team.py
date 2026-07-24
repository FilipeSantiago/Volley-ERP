from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class TeamStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Team(BaseModel):
    team_id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str | None = None
    gender: str | None = None
    status: TeamStatus = TeamStatus.ACTIVE
    team_spreadsheet_id: str | None = None
    team_spreadsheet_url: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)



def _ensure_aware_datetime(value: Any) -> Any:
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

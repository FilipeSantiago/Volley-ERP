from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class AthleteTeamRelationshipStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRANSFERRED = "transferred"


class AthleteTeamRelationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    athlete_id: str = Field(min_length=1)
    status: AthleteTeamRelationshipStatus = AthleteTeamRelationshipStatus.ACTIVE
    joined_at: datetime
    left_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("joined_at", "left_at", "created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)

    @model_validator(mode="after")
    def validate_timeline(self) -> "AthleteTeamRelationship":
        if self.left_at is not None and self.left_at < self.joined_at:
            raise ValueError("left_at must be greater than or equal to joined_at.")
        return self



def _ensure_aware_datetime(value: Any) -> Any:
    if value is None or not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

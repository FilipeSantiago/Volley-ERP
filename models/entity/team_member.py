from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from models.entity.organization_member import MembershipStatus


class TeamRole(str, Enum):
    TEAM_ADMIN = "TEAM_ADMIN"
    COACH = "COACH"
    ASSISTANT = "ASSISTANT"
    PLAYER = "PLAYER"
    VIEWER = "VIEWER"


class TeamMember(BaseModel):
    org_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    email: str | None = None
    team_role: TeamRole
    status: MembershipStatus = MembershipStatus.ACTIVE
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

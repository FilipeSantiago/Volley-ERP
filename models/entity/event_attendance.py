from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class EventAttendanceStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    ABSENT = "ABSENT"
    PENDING = "PENDING"


class EventAttendance(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    team_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    athlete_id: str = Field(min_length=1)
    status: EventAttendanceStatus = EventAttendanceStatus.PENDING
    checked_in_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("checked_in_at", "created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        if value is None or not isinstance(value, datetime):
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime values must be timezone-aware.")
        return value

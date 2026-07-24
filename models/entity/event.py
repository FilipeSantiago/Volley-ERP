from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class EventType(str, Enum):
    TRAINING = "TRAINING"
    GAME = "GAME"
    TOURNAMENT = "TOURNAMENT"
    FRIENDLY = "FRIENDLY"
    MEETING = "MEETING"
    OTHER = "OTHER"


class EventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class CalendarSyncStatus(str, Enum):
    NOT_SYNCED = "NOT_SYNCED"
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    team_id: str = Field(min_length=1)
    event_type: EventType
    title: str = Field(min_length=1)
    description: str | None = None
    starts_at: datetime
    ends_at: datetime
    location: str | None = None
    status: EventStatus = EventStatus.SCHEDULED
    google_calendar_id: str | None = None
    google_event_id: str | None = None
    calendar_sync_status: CalendarSyncStatus = CalendarSyncStatus.NOT_SYNCED
    calendar_sync_error: str | None = None
    created_by: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("starts_at", "ends_at", "created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        if not isinstance(value, datetime):
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime values must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def validate_time_window(self) -> "Event":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at.")
        return self

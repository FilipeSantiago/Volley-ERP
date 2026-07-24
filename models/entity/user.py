from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class User(BaseModel):
    user_id: str = Field(default_factory=lambda: str(uuid4()))
    google_sub: str = Field(min_length=1)
    email: str | None = None
    name: str | None = None
    is_active: bool = True
    avatar_url: str | None = None
    phone: str | None = None
    locale: str | None = None
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime

    @field_validator("created_at", "updated_at", "last_login_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)



def _ensure_aware_datetime(value: Any) -> Any:
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

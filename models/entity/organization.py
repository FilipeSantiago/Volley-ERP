from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Organization(BaseModel):
    org_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(min_length=1)
    owner_user_id: str | None = None
    storage_owner_user_id: str | None = None
    workspace_root_folder_id: str | None = None
    workspace_sheets_folder_id: str | None = None
    workspace_images_folder_id: str | None = None
    workspace_exports_folder_id: str | None = None
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

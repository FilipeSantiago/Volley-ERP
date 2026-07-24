from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ExternalAuthProvider(str, Enum):
    GOOGLE = "google"


class ConnectionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    FAILED = "FAILED"


class GoogleConnection(BaseModel):
    user_id: str = Field(min_length=1)
    provider: ExternalAuthProvider = ExternalAuthProvider.GOOGLE
    encrypted_refresh_token: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=list)
    google_email: str | None = None
    connection_status: ConnectionStatus = ConnectionStatus.ACTIVE
    token_last_refreshed_at: datetime | None = None
    last_oauth_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "created_at",
        "updated_at",
        "token_last_refreshed_at",
        "last_oauth_login_at",
        mode="before",
    )
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)

    @field_validator("scopes", mode="before")
    @classmethod
    def normalize_scopes(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("scopes must be a list.")
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def validate_connection(self) -> "GoogleConnection":
        if not self.scopes:
            raise ValueError("scopes must not be empty.")
        return self



def _ensure_aware_datetime(value: Any) -> Any:
    if value is None or not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

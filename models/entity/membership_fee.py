from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.enums import MonthlyFeeDirection, MonthlyFeeTag

_BR_CENTS = Decimal("0.01")
RECURRING_MONTHLY_FEE_SOURCE = "RECURRING_RULE"
MONTHLY_FEE_TAG_TO_DIRECTION = {
    MonthlyFeeTag.MONTHLY_CONTRIBUTION: MonthlyFeeDirection.CREDIT,
    MonthlyFeeTag.COACH: MonthlyFeeDirection.DEBIT,
    MonthlyFeeTag.COMMISSION: MonthlyFeeDirection.DEBIT,
    MonthlyFeeTag.COURT: MonthlyFeeDirection.DEBIT,
}


class MembershipFeeSource(str, Enum):
    RECURRING_RULE = RECURRING_MONTHLY_FEE_SOURCE


class MembershipFee(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    org_id: str | None = None
    team_id: str = Field(min_length=1)
    tag: MonthlyFeeTag
    direction: MonthlyFeeDirection | None = None
    amount: Decimal
    currency: str = Field(default="BRL", min_length=1)
    athlete_id: str | None = None
    person_name: str | None = None
    description: str | None = None
    source: MembershipFeeSource = MembershipFeeSource.RECURRING_RULE
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def compat_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if payload.get("id") is None:
            payload["id"] = payload.get("fee_id") or payload.get("entry_id") or str(uuid4())
        if payload.get("active") is None and "is_active" in payload:
            payload["active"] = payload.get("is_active")
        return payload

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        return _normalize_money(value, minimum=Decimal("0.00"))

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        normalized = str(value or "BRL").strip().upper()
        return normalized or "BRL"

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        if value is None or not isinstance(value, datetime):
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime values must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def validate_business_rules(self) -> "MembershipFee":
        expected_direction = MONTHLY_FEE_TAG_TO_DIRECTION[self.tag]
        if self.direction is None:
            self.direction = expected_direction
        if self.direction != expected_direction:
            raise ValueError("direction does not match tag.")
        if self.tag == MonthlyFeeTag.MONTHLY_CONTRIBUTION and not self.athlete_id:
            raise ValueError("athlete_id is required for MONTHLY_CONTRIBUTION.")
        if self.tag == MonthlyFeeTag.COACH and self.athlete_id is not None:
            raise ValueError("athlete_id is not allowed for COACH.")
        if self.tag == MonthlyFeeTag.COMMISSION:
            if self.athlete_id is not None:
                raise ValueError("athlete_id is not allowed for COMMISSION.")
            if not self.person_name:
                raise ValueError("person_name is required for COMMISSION.")
        if self.tag == MonthlyFeeTag.COURT:
            if self.athlete_id is not None or self.person_name is not None:
                raise ValueError("athlete_id/person_name are not allowed for COURT.")
        return self

    @property
    def fee_id(self) -> str:
        return self.id

    @property
    def is_active(self) -> bool:
        return self.active

    @property
    def recurrence_key(self) -> str | None:
        prefix = f"{self.team_id}|{self.tag.value}"
        if not self.active or self.source != MembershipFeeSource.RECURRING_RULE:
            return None
        if self.tag == MonthlyFeeTag.MONTHLY_CONTRIBUTION:
            return f"{prefix}|athlete|{self.athlete_id}" if self.athlete_id else None
        if self.tag == MonthlyFeeTag.COACH:
            if self.person_name:
                return f"{prefix}|person_name|{self.person_name.lower()}"
            return prefix
        if self.tag == MonthlyFeeTag.COMMISSION:
            return (
                f"{prefix}|person_name|{self.person_name.lower()}"
                if self.person_name
                else None
            )
        if self.tag == MonthlyFeeTag.COURT:
            return prefix
        return None


def _normalize_money(value: Any, *, minimum: Decimal) -> Decimal:
    normalized = Decimal(str(value).replace(",", "."))
    normalized = normalized.quantize(_BR_CENTS, rounding=ROUND_HALF_UP)
    if normalized < minimum:
        raise ValueError(f"amount must be greater than or equal to {minimum}.")
    return normalized

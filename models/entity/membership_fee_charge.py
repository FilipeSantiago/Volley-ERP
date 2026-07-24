from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

_BR_CENTS = Decimal("0.01")


class MembershipFeeChargeStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    WAIVED = "WAIVED"
    CANCELLED = "CANCELLED"


class MembershipFeeCharge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    team_id: str = Field(min_length=1)
    athlete_id: str = Field(min_length=1)
    membership_fee_id: str = Field(min_length=1)
    reference_month: date
    amount_due: Decimal
    currency: str = Field(default="BRL", min_length=1)
    due_date: date
    status: MembershipFeeChargeStatus = MembershipFeeChargeStatus.PENDING
    financial_entry_id: str | None = None
    payer_person_id: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    notes: str | None = None

    @field_validator("reference_month", mode="before")
    @classmethod
    def normalize_reference_month(cls, value: Any) -> date:
        if isinstance(value, datetime):
            value = value.date()
        if not isinstance(value, date):
            raise ValueError("reference_month must be a date.")
        return value.replace(day=1)

    @field_validator("amount_due", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        normalized = Decimal(str(value).replace(",", "."))
        normalized = normalized.quantize(_BR_CENTS, rounding=ROUND_HALF_UP)
        if normalized <= Decimal("0.00"):
            raise ValueError("amount_due must be greater than zero.")
        return normalized

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        normalized = str(value or "BRL").strip().upper()
        return normalized or "BRL"

    @field_validator("created_at", "updated_at", "paid_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)

    @model_validator(mode="after")
    def validate_status(self) -> "MembershipFeeCharge":
        if self.status == MembershipFeeChargeStatus.PAID:
            if not self.payer_person_id:
                raise ValueError("PAID charges require payer_person_id.")
            if self.paid_at is None:
                raise ValueError("PAID charges require paid_at.")
            if not self.financial_entry_id:
                raise ValueError("PAID charges require financial_entry_id.")
        return self

    @property
    def logical_key(self) -> tuple[str, str, date]:
        return (self.team_id, self.athlete_id, self.reference_month)


def _ensure_aware_datetime(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from models.enums import MonthlyFeeDirection

_BR_CENTS = Decimal("0.01")


class FinancialEntryStatus(str, Enum):
    PENDING = "PENDING"
    SETTLED = "SETTLED"
    CANCELLED = "CANCELLED"


class FinancialEntrySource(str, Enum):
    RECURRING_RULE = "RECURRING_RULE"
    MEMBERSHIP_FEE_CHARGE = "MEMBERSHIP_FEE_CHARGE"
    EVENT_COST = "EVENT_COST"
    MANUAL = "MANUAL"
    ADJUSTMENT = "ADJUSTMENT"


class FinancialEntryCategory(str, Enum):
    MONTHLY_CONTRIBUTION = "MONTHLY_CONTRIBUTION"
    COACH_TRAINING = "COACH_TRAINING"
    COACH_GAME = "COACH_GAME"
    COACH = "COACH"
    COMMISSION = "COMMISSION"
    COURT = "COURT"
    REFEREE = "REFEREE"
    TOURNAMENT = "TOURNAMENT"
    EQUIPMENT = "EQUIPMENT"
    TRANSPORTATION = "TRANSPORTATION"
    OTHER = "OTHER"


class FinancialEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    team_id: str = Field(min_length=1)
    direction: MonthlyFeeDirection
    category: FinancialEntryCategory
    status: FinancialEntryStatus = FinancialEntryStatus.PENDING
    description: str = Field(min_length=1)
    amount: Decimal
    currency: str = Field(default="BRL", min_length=1)
    competence_date: date
    due_date: date | None = None
    settled_at: datetime | None = None
    counterparty_person_id: str | None = None
    source: FinancialEntrySource = FinancialEntrySource.MANUAL
    source_id: str | None = None
    event_id: str | None = None
    created_by: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    notes: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        return _normalize_money(value, minimum=Decimal("0.01"))

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        normalized = str(value or "BRL").strip().upper()
        return normalized or "BRL"

    @field_validator("created_at", "updated_at", "settled_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        return _ensure_aware_datetime(value)

    @model_validator(mode="after")
    def validate_business_rules(self) -> "FinancialEntry":
        if self.status == FinancialEntryStatus.SETTLED and self.settled_at is None:
            raise ValueError("SETTLED entries require settled_at.")
        if self.status == FinancialEntryStatus.PENDING and self.settled_at is not None:
            raise ValueError("PENDING entries must not define settled_at.")
        if self.status == FinancialEntryStatus.CANCELLED and self.settled_at is not None:
            raise ValueError("CANCELLED entries must not define settled_at.")
        if self.source == FinancialEntrySource.EVENT_COST:
            if not self.source_id:
                raise ValueError("EVENT_COST entries require source_id.")
            if not self.event_id:
                raise ValueError("EVENT_COST entries require event_id.")
        if self.source == FinancialEntrySource.MEMBERSHIP_FEE_CHARGE and not self.source_id:
            raise ValueError("MEMBERSHIP_FEE_CHARGE entries require source_id.")
        return self


def _normalize_money(value: Any, *, minimum: Decimal) -> Decimal:
    normalized = Decimal(str(value).replace(",", "."))
    normalized = normalized.quantize(_BR_CENTS, rounding=ROUND_HALF_UP)
    if normalized < minimum:
        raise ValueError(f"amount must be greater than or equal to {minimum}.")
    return normalized


def _ensure_aware_datetime(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value

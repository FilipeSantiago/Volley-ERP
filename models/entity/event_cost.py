from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

_BR_CENTS = Decimal("0.01")


class EventCostType(str, Enum):
    COACH_TRAINING = "COACH_TRAINING"
    COACH_GAME = "COACH_GAME"
    COURT = "COURT"
    REFEREE = "REFEREE"
    TOURNAMENT = "TOURNAMENT"
    TRANSPORTATION = "TRANSPORTATION"
    OTHER = "OTHER"


class EventCost(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    team_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    cost_type: EventCostType
    description: str = Field(min_length=1)
    quantity: Decimal = Field(default=Decimal("1.00"))
    unit_amount: Decimal
    total_amount: Decimal | None = None
    currency: str = Field(default="BRL", min_length=1)
    payee_person_id: str | None = None
    financial_entry_id: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None = None

    @field_validator("quantity", mode="before")
    @classmethod
    def normalize_quantity(cls, value: Any) -> Decimal:
        normalized = Decimal(str(value or "1").replace(",", "."))
        normalized = normalized.quantize(_BR_CENTS, rounding=ROUND_HALF_UP)
        if normalized <= Decimal("0.00"):
            raise ValueError("quantity must be greater than zero.")
        return normalized

    @field_validator("unit_amount", "total_amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        normalized = Decimal(str(value).replace(",", "."))
        normalized = normalized.quantize(_BR_CENTS, rounding=ROUND_HALF_UP)
        if normalized < Decimal("0.00"):
            raise ValueError("monetary values cannot be negative.")
        return normalized

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        normalized = str(value or "BRL").strip().upper()
        return normalized or "BRL"

    @field_validator("created_at", "updated_at", "cancelled_at", mode="before")
    @classmethod
    def validate_timestamps(cls, value: Any) -> Any:
        if value is None or not isinstance(value, datetime):
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime values must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def validate_total(self) -> "EventCost":
        expected_total = (self.quantity * self.unit_amount).quantize(
            _BR_CENTS,
            rounding=ROUND_HALF_UP,
        )
        if self.total_amount is None:
            self.total_amount = expected_total
        if self.total_amount != expected_total:
            raise ValueError("total_amount must equal quantity * unit_amount.")
        return self

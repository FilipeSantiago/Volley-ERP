from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_validator

_BR_CENTS = Decimal("0.01")


class CashflowCategorySummary(BaseModel):
    category: str
    expected_amount: Decimal = Field(default=Decimal("0.00"))
    realized_amount: Decimal = Field(default=Decimal("0.00"))

    @field_validator("expected_amount", "realized_amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        return _normalize_money(value)


class MembershipFeeCashflowItem(BaseModel):
    membership_fee_charge_id: str
    athlete_id: str
    athlete_name: str | None = None
    amount_due: Decimal
    status: str
    due_date: date | None = None
    paid_at: date | None = None

    @field_validator("amount_due", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        return _normalize_money(value)


class EventCostCashflowItem(BaseModel):
    event_cost_id: str
    event_id: str
    description: str
    amount: Decimal
    status: str

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        return _normalize_money(value)


class CashflowEntryItem(BaseModel):
    financial_entry_id: str
    direction: str
    category: str
    status: str
    amount: Decimal
    competence_date: date
    settled_at: date | None = None
    description: str

    @field_validator("amount", mode="before")
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        return _normalize_money(value)


class CashflowSummary(BaseModel):
    reference_month: date
    expected_credits: Decimal = Field(default=Decimal("0.00"))
    received_credits: Decimal = Field(default=Decimal("0.00"))
    pending_credits: Decimal = Field(default=Decimal("0.00"))
    expected_debits: Decimal = Field(default=Decimal("0.00"))
    paid_debits: Decimal = Field(default=Decimal("0.00"))
    pending_debits: Decimal = Field(default=Decimal("0.00"))
    outstanding_membership_fees: Decimal = Field(default=Decimal("0.00"))
    overdue_membership_fees: Decimal = Field(default=Decimal("0.00"))
    membership_fee_paid_count: int = 0
    membership_fee_pending_count: int = 0
    training_count: int = 0
    game_count: int = 0
    training_cost_total: Decimal = Field(default=Decimal("0.00"))
    game_cost_total: Decimal = Field(default=Decimal("0.00"))

    @field_validator("reference_month", mode="before")
    @classmethod
    def normalize_reference_month(cls, value: Any) -> date:
        if not isinstance(value, date):
            raise ValueError("reference_month must be a date.")
        return value.replace(day=1)

    @field_validator(
        "expected_credits",
        "received_credits",
        "pending_credits",
        "expected_debits",
        "paid_debits",
        "pending_debits",
        "outstanding_membership_fees",
        "overdue_membership_fees",
        "training_cost_total",
        "game_cost_total",
        mode="before",
    )
    @classmethod
    def normalize_amount(cls, value: Any) -> Decimal:
        return _normalize_money(value)

    @computed_field
    @property
    def expected_balance(self) -> Decimal:
        return _normalize_money(self.expected_credits - self.expected_debits)

    @computed_field
    @property
    def realized_balance(self) -> Decimal:
        return _normalize_money(self.received_credits - self.paid_debits)


def _normalize_money(value: Any) -> Decimal:
    normalized = Decimal(str(value or "0").replace(",", "."))
    return normalized.quantize(_BR_CENTS, rounding=ROUND_HALF_UP)

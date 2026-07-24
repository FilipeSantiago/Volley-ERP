from typing import Any

from pydantic import BaseModel, Field, model_validator

from models.enums import MonthlyFeeDirection, MonthlyFeeTag


class MonthlyFeeListQuery(BaseModel):
    team_id: str = Field(min_length=1)
    tag: MonthlyFeeTag | None = None
    athlete_id: str | None = None
    include_inactive: bool = False


class MonthlyFeeCreateRequest(BaseModel):
    team_id: str | None = Field(default=None, min_length=1)
    tag: MonthlyFeeTag
    amount: float = Field(ge=0)
    currency: str | None = Field(default=None, min_length=1)
    athlete_id: str | None = None
    person_name: str | None = None
    description: str | None = None


class MonthlyFeeUpdateRequest(BaseModel):
    team_id: str | None = Field(default=None, min_length=1)
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=1)
    description: str | None = None

    @model_validator(mode="after")
    def validate_has_mutation_fields(self) -> "MonthlyFeeUpdateRequest":
        if self.amount is None and self.currency is None and self.description is None:
            raise ValueError("At least one of amount, currency or description must be provided.")
        return self


class MonthlyFeeEntry(BaseModel):
    fee_id: str
    org_id: str
    team_id: str
    tag: MonthlyFeeTag
    direction: MonthlyFeeDirection
    amount: float
    currency: str
    athlete_id: str | None = None
    person_name: str | None = None
    description: str | None = None
    source: str
    is_active: bool
    created_at: str
    updated_at: str

    @model_validator(mode="before")
    @classmethod
    def normalize_amount(cls, value: Any):
        if not isinstance(value, dict):
            return value
        amount_value = value.get("amount")
        if isinstance(amount_value, str):
            try:
                value = {**value, "amount": float(amount_value)}
            except ValueError:
                return value
        return value


class MonthlyFeeListResponse(BaseModel):
    items: list[MonthlyFeeEntry]
    count: int

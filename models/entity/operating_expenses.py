from __future__ import annotations

from pydantic import Field, model_validator

from models.entity.financial_entry import FinancialEntry, FinancialEntrySource
from models.enums import MonthlyFeeDirection


class OperatingExpense(FinancialEntry):
    """Compatibility wrapper for debit-side manual financial entries.

    Operating expenses are represented directly by FinancialEntry and do not form a
    separate ledger in the domain model.
    """

    direction: MonthlyFeeDirection = Field(default=MonthlyFeeDirection.DEBIT)
    source: FinancialEntrySource = Field(default=FinancialEntrySource.MANUAL)

    @model_validator(mode="after")
    def validate_operating_expense(self) -> "OperatingExpense":
        if self.direction != MonthlyFeeDirection.DEBIT:
            raise ValueError("OperatingExpense must use DEBIT direction.")
        return self

from enum import Enum


class MonthlyFeeDirection(str, Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"

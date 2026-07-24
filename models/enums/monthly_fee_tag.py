from enum import Enum


class MonthlyFeeTag(str, Enum):
    MONTHLY_CONTRIBUTION = "MONTHLY_CONTRIBUTION"
    COACH = "COACH"
    COMMISSION = "COMMISSION"
    COURT = "COURT"

"""Holdings validations (REQ-002): row count and "as of" date."""

from datetime import date

from scraper.details import EtfDetails
from validators.common import FieldResult, Status, check_date, new_reasons, resolve


def validate_holdings(details: EtfDetails, run_date: date, max_age: int) -> FieldResult:
    if details.holdings_rows is None:
        return FieldResult(Status.MISSING, ["holdings table not available"])
    if details.holdings_date is None:
        return FieldResult(Status.MISSING, ["holdings 'As of' date not available"])

    reasons = new_reasons()
    if details.holdings_rows == 0:
        reasons[Status.INCORRECT].append("holdings table has no rows")
    check_date("Holdings", details.holdings_date, run_date, max_age, reasons)
    return resolve(reasons)

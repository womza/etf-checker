"""NAV validations (REQ-002)."""

from datetime import date

from scraper.details import EtfDetails
from validators.common import FieldResult, Status, check_date, new_reasons, resolve
from validators.consistency import check_premium_discount


def validate_nav(details: EtfDetails, run_date: date, max_age: int) -> FieldResult:
    return validate_price_field("NAV", details.nav, details.nav_date, details, run_date, max_age)


def validate_price_field(name, value, value_date, details, run_date, max_age) -> FieldResult:
    """Rules shared by NAV and Market Price."""
    if value is None:
        return FieldResult(Status.MISSING, [f"{name} not available"])

    reasons = new_reasons()
    if value <= 0:
        reasons[Status.INCORRECT].append(f"{name} ${value} is not positive")
    check_date(name, value_date, run_date, max_age, reasons)

    if details.nav is not None and details.price is not None and details.nav > 0 and details.price > 0:
        status, reason = check_premium_discount(details)
        if reason:
            reasons[status].append(reason)
    else:
        reasons[Status.NOT_VERIFIABLE].append("NAV/Price cross-check needs both values")

    return resolve(reasons)

"""Market Price validations (REQ-002). Same rules as NAV."""

from datetime import date

from scraper.details import EtfDetails
from validators.common import FieldResult
from validators.nav import validate_price_field


def validate_price(details: EtfDetails, run_date: date, max_age: int) -> FieldResult:
    return validate_price_field(
        "Market Price", details.price, details.price_date, details, run_date, max_age
    )

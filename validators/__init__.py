"""Validation of extracted data (independent from extraction). See REQ-002."""

from dataclasses import dataclass
from datetime import date

import config
from scraper.details import EtfDetails
from validators.common import FieldResult, Status
from validators.duration import validate_duration
from validators.holdings import validate_holdings
from validators.nav import validate_nav
from validators.price import validate_price


@dataclass
class EtfValidation:
    nav: FieldResult
    price: FieldResult
    duration: FieldResult
    holdings: FieldResult

    def fields(self) -> dict[str, FieldResult]:
        return {"NAV": self.nav, "Price": self.price, "Duration": self.duration, "Holdings": self.holdings}

    @property
    def ok(self) -> bool:
        """False when any field is MISSING or INCORRECT (shown as ✗)."""
        return not any(result.is_error for result in self.fields().values())


def validate_etf(
    details: EtfDetails | None,
    run_date: date,
    max_age: int = config.MAX_DATA_AGE_BUSINESS_DAYS,
) -> EtfValidation:
    """Validate one ETF. `details` is None when the page could not be used."""
    details = details or EtfDetails()
    return EtfValidation(
        nav=validate_nav(details, run_date, max_age),
        price=validate_price(details, run_date, max_age),
        duration=validate_duration(details),
        holdings=validate_holdings(details, run_date, max_age),
    )


__all__ = ["EtfValidation", "FieldResult", "Status", "validate_etf"]

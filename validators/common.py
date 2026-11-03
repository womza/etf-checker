"""Shared validation types and helpers (docs/requirements/REQ-002-validations.md)."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum


class Status(str, Enum):
    VERIFIED = "VERIFIED"
    INCORRECT = "INCORRECT"
    MISSING = "MISSING"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Portfolio Duration not published: not an error


ERROR_STATUSES = {Status.INCORRECT, Status.MISSING}
SITE_DATE_FORMAT = "%m/%d/%Y"


@dataclass
class FieldResult:
    """Validation outcome of one field. `reasons` explain any non-VERIFIED status."""

    status: Status
    reasons: list[str] = field(default_factory=list)

    @property
    def is_error(self) -> bool:
        return self.status in ERROR_STATUSES


def resolve(reasons_by_status: dict[Status, list[str]]) -> FieldResult:
    """Pick the most severe status that has reasons: INCORRECT > NOT_VERIFIABLE > VERIFIED."""
    for status in (Status.INCORRECT, Status.NOT_VERIFIABLE):
        if reasons_by_status.get(status):
            reasons = reasons_by_status[Status.INCORRECT] + reasons_by_status[Status.NOT_VERIFIABLE]
            return FieldResult(status, reasons)
    return FieldResult(Status.VERIFIED)


def new_reasons() -> dict[Status, list[str]]:
    return {Status.INCORRECT: [], Status.NOT_VERIFIABLE: []}


def parse_site_date(text: str | None) -> date | None:
    """Parse a date as shown on the site (MM/DD/YYYY). None if absent or another format."""
    if not text:
        return None
    try:
        return datetime.strptime(text.strip(), SITE_DATE_FORMAT).date()
    except ValueError:
        return None


def business_days_between(start: date, end: date) -> int:
    """Weekdays after `start` up to and including `end` (no holiday calendar)."""
    days, current = 0, start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def check_date(
    name: str,
    text: str | None,
    run_date: date,
    max_age: int,
    reasons: dict[Status, list[str]],
) -> date | None:
    """Freshness rules shared by NAV, Market Price and holdings dates."""
    if text is None:
        reasons[Status.NOT_VERIFIABLE].append(f"{name} date not found")
        return None
    parsed = parse_site_date(text)
    if parsed is None:
        reasons[Status.NOT_VERIFIABLE].append(f"{name} date {text!r} is not MM/DD/YYYY")
        return None
    if parsed > run_date:
        reasons[Status.INCORRECT].append(f"{name} date {text} is in the future")
    else:
        age = business_days_between(parsed, run_date)
        if age > max_age:
            reasons[Status.INCORRECT].append(
                f"{name} date {text} is stale ({age} business days old, max {max_age})"
            )
    return parsed

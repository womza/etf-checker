"""Portfolio Duration validations (REQ-002).

Any sign is valid (e.g. PFIX is negative) and no fixed range is used. The site
publishes no date or second source for the duration, so a readable value can
only be NOT_VERIFIABLE.
"""

from scraper.details import EtfDetails
from validators.common import FieldResult, Status


def validate_duration(details: EtfDetails) -> FieldResult:
    if not details.duration_published:
        return FieldResult(Status.NOT_APPLICABLE)
    if details.duration is None:
        return FieldResult(Status.MISSING, [f"Portfolio Duration unreadable ({details.duration_raw!r})"])
    return FieldResult(Status.NOT_VERIFIABLE, ["no reference source for Portfolio Duration"])

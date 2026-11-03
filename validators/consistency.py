"""Cross-check between NAV, Market Price and the published Premium/Discount (%).

Premium/Discount = (Market Price - NAV) / NAV * 100.

The site shows NAV and Market Price rounded to cents and the percentage rounded
to 2 decimals, so the check accepts any published value that can be produced by
some NAV and price within half a cent of the shown values (plus half a basis
point for the percentage rounding). No arbitrary tolerance is used.
"""

from decimal import Decimal

from scraper.details import EtfDetails
from validators.common import Status, parse_site_date

PRICE_ROUNDING = Decimal("0.005")  # values shown with 2 decimals
PERCENT_ROUNDING = Decimal("0.005")


def premium_bounds(nav: Decimal, price: Decimal) -> tuple[Decimal, Decimal]:
    """Smallest and largest premium (%) compatible with the rounded NAV and price."""
    nav_low, nav_high = nav - PRICE_ROUNDING, nav + PRICE_ROUNDING
    price_low, price_high = price - PRICE_ROUNDING, price + PRICE_ROUNDING
    low = (price_low - nav_high) / nav_high * 100
    high = (price_high - nav_low) / nav_low * 100
    return low - PERCENT_ROUNDING, high + PERCENT_ROUNDING


def check_premium_discount(details: EtfDetails) -> tuple[Status, str | None]:
    """Return (VERIFIED, None), (INCORRECT, reason) or (NOT_VERIFIABLE, reason).

    Only meaningful when NAV and price are both present and positive.
    """
    if details.premium_discount is None:
        return Status.NOT_VERIFIABLE, "Premium/Discount not published, NAV/Price cross-check skipped"

    dates = {details.nav_date, details.price_date, details.premium_date}
    if len(dates) != 1 or parse_site_date(details.nav_date) is None:
        return Status.NOT_VERIFIABLE, (
            f"NAV/Price/Premium dates differ or unknown ({details.nav_date}, "
            f"{details.price_date}, {details.premium_date}), cross-check skipped"
        )

    low, high = premium_bounds(details.nav, details.price)
    computed = (details.price - details.nav) / details.nav * 100
    if low <= details.premium_discount <= high:
        return Status.VERIFIED, None
    return Status.INCORRECT, (
        f"NAV ${details.nav} and Price ${details.price} give a premium of {computed:.3f}% "
        f"but the site shows {details.premium_raw} (accepted range {low:.3f}% to {high:.3f}%)"
    )

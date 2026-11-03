"""Extraction of data from each ETF detail page.

Sources (verified against the live site on 2026-11-02):
- Fund Overview rows `div.c-fund-overview__row` (label / value cells):
    "Ticker Symbol"                    -> AGGH
    "NAV Per Share as of 10/30/2026"   -> $19.21
    "Market Price as of 10/30/2026"    -> $19.27
    "Portfolio Duration"               -> 7.40 (only fixed-income ETFs; may be negative)
    "Premium/Discount (%) as of 10/30/2026" -> 0.33% (used by Phase 5 cross-checks;
                                              may carry a footnote marker, e.g. "-1.59% *")
- Holdings pane `#holdings-table-pane`:
    `p.o-etfs__date`                   -> "As of 10/30/2026"
    `table tbody tr`                   -> one row per holding

Missing data rules (see README and docs/requirements/REQ-001):
- NAV / Market Price shown as "N/A" on the site -> no value, MISSING.
- Holdings table not rendered on the page -> no row count, MISSING.
- Portfolio Duration not published -> not applicable (not an error).
Values are never invented: anything that cannot be read is left as None
and the reason is recorded in `EtfDetails.issues`.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

OVERVIEW_ROW_SELECTOR = "div.c-fund-overview__row"
OVERVIEW_LABEL_SELECTOR = "div.c-fund-overview__cell-header"
OVERVIEW_VALUE_SELECTOR = "div.c-fund-overview__cell-data"

TICKER_LABEL = "Ticker Symbol"
NAV_LABEL_PREFIX = "NAV Per Share"
PRICE_LABEL_PREFIX = "Market Price"
DURATION_LABEL = "Portfolio Duration"
PREMIUM_LABEL_PREFIX = "Premium/Discount"

HOLDINGS_PANE_SELECTOR = "#holdings-table-pane"
HOLDINGS_DATE_SELECTOR = "p.o-etfs__date"
HOLDINGS_TABLE_SELECTOR = "table"

AS_OF_PATTERN = re.compile(r"\bas of\s+(.+)$", re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*%")
NOT_AVAILABLE_TEXTS = {"N/A", "NA", "-", "—", ""}


@dataclass
class EtfDetails:
    """Data read from one detail page. None means "not available"."""

    page_ticker: str | None = None

    nav: Decimal | None = None
    nav_raw: str | None = None
    nav_date: str | None = None

    price: Decimal | None = None
    price_raw: str | None = None
    price_date: str | None = None

    duration_published: bool = False
    duration: Decimal | None = None
    duration_raw: str | None = None

    # Optional, only used for cross-checks: its absence is not an extraction issue
    premium_discount: Decimal | None = None  # percent, e.g. Decimal("0.33")
    premium_raw: str | None = None
    premium_date: str | None = None

    holdings_rows: int | None = None
    holdings_date: str | None = None

    issues: list[str] = field(default_factory=list)


def parse_fund_overview(soup: BeautifulSoup) -> dict[str, str]:
    """Return the Fund Overview label/value pairs exactly as shown on the page."""
    overview: dict[str, str] = {}
    for row in soup.select(OVERVIEW_ROW_SELECTOR):
        label = row.select_one(OVERVIEW_LABEL_SELECTOR)
        value = row.select_one(OVERVIEW_VALUE_SELECTOR)
        if label is None or value is None:
            continue
        key = " ".join(label.get_text(" ", strip=True).split())
        if key and key not in overview:
            overview[key] = " ".join(value.get_text(" ", strip=True).split())
    return overview


def parse_page_ticker(html: str) -> str | None:
    """Return the 'Ticker Symbol' shown in the Fund Overview, or None if absent."""
    overview = parse_fund_overview(BeautifulSoup(html, "html.parser"))
    return _ticker_from_overview(overview)


def parse_details(html: str) -> EtfDetails:
    """Extract NAV, Market Price, Portfolio Duration and holdings info from a detail page."""
    soup = BeautifulSoup(html, "html.parser")
    overview = parse_fund_overview(soup)
    details = EtfDetails(page_ticker=_ticker_from_overview(overview))

    # NAV
    label, raw = _find_by_prefix(overview, NAV_LABEL_PREFIX)
    details.nav_raw, details.nav_date = raw, _as_of_date(label)
    details.nav = _parse_number(raw, "NAV", details.issues, money=True)

    # Market Price
    label, raw = _find_by_prefix(overview, PRICE_LABEL_PREFIX)
    details.price_raw, details.price_date = raw, _as_of_date(label)
    details.price = _parse_number(raw, "Market Price", details.issues, money=True)

    # Portfolio Duration (absent or "N/A" -> not applicable, not an error)
    raw = overview.get(DURATION_LABEL)
    details.duration_raw = raw
    if raw is not None and raw.strip().upper() not in NOT_AVAILABLE_TEXTS:
        details.duration_published = True
        details.duration = _parse_number(raw, "Portfolio Duration", details.issues)

    # Premium/Discount (%) (optional)
    label, raw = _find_by_prefix(overview, PREMIUM_LABEL_PREFIX)
    details.premium_raw, details.premium_date = raw, _as_of_date(label)
    match = PERCENT_PATTERN.match(raw or "")
    details.premium_discount = Decimal(match.group(1)) if match else None

    # Holdings
    pane = soup.select_one(HOLDINGS_PANE_SELECTOR)
    if pane is None:
        details.issues.append(f"Holdings: section not found ({HOLDINGS_PANE_SELECTOR})")
        return details

    table = pane.select_one(HOLDINGS_TABLE_SELECTOR)
    if table is None:
        details.issues.append("Holdings: no table on page")
    else:
        # Only rows with data cells count (skips "no results" placeholders)
        details.holdings_rows = sum(
            1 for row in table.select("tbody tr") if row.find("td") and not _is_empty_row(row)
        )

    date_el = pane.select_one(HOLDINGS_DATE_SELECTOR)
    date_text = date_el.get_text(" ", strip=True) if date_el else ""
    details.holdings_date = _strip_as_of(date_text) or None
    if details.holdings_date is None:
        details.issues.append(f"Holdings: 'As of' date not found ({HOLDINGS_DATE_SELECTOR})")

    return details


def _ticker_from_overview(overview: dict[str, str]) -> str | None:
    ticker = overview.get(TICKER_LABEL)
    return ticker.upper() if ticker else None


def _find_by_prefix(overview: dict[str, str], prefix: str) -> tuple[str | None, str | None]:
    """Return (label, value) of the first overview row whose label starts with prefix."""
    for label, value in overview.items():
        if label.startswith(prefix):
            return label, value
    return None, None


def _as_of_date(label: str | None) -> str | None:
    """Date part of a label like 'NAV Per Share as of 10/30/2026', as shown on the site."""
    if not label:
        return None
    match = AS_OF_PATTERN.search(label)
    return match.group(1).strip() if match else None


def _strip_as_of(text: str) -> str:
    """'As of 10/30/2026' -> '10/30/2026' (no reformatting)."""
    match = AS_OF_PATTERN.search(text)
    return match.group(1).strip() if match else ""


def _is_empty_row(row) -> bool:
    cells = row.find_all("td")
    return len(cells) == 1 and cells[0].get("colspan") is not None


def _parse_number(raw: str | None, name: str, issues: list[str], money: bool = False) -> Decimal | None:
    """Parse '$1,234.56' / '-28.53' into a Decimal. Records the reason when it fails."""
    if raw is None:
        issues.append(f"{name}: field not found on page")
        return None
    text = raw.strip()
    if text.upper() in NOT_AVAILABLE_TEXTS:
        issues.append(f"{name}: site shows {text or 'an empty value'!r}")
        return None
    cleaned = text.replace(",", "").replace(" ", "")
    if money:
        cleaned = cleaned.replace("$", "", 1)
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        issues.append(f"{name}: unparseable value {text!r}")
        return None
    if not value.is_finite():
        issues.append(f"{name}: unparseable value {text!r}")
        return None
    return value

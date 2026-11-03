"""Extraction of the ETF list from the provider's listing page (BASE_URL/etfs).

Source (identified in Phase 1): the overview table `table.c-etfs-landing__overview`.
Each body row holds the ticker and detail URL in `td.views-field-field-ticker-symbol a`
and the fund name in `td.views-field-title`.
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

TABLE_SELECTOR = "table.c-etfs-landing__overview"
TICKER_SELECTOR = "td.views-field-field-ticker-symbol a"
NAME_SELECTOR = "td.views-field-title"

TICKER_PATTERN = re.compile(r"^[A-Z]{1,6}$")


class ListingParseError(Exception):
    """Raised when the listing page does not have the expected structure."""


@dataclass(frozen=True)
class EtfListing:
    ticker: str
    name: str
    url: str


def parse_listing(html: str, base_url: str = config.BASE_URL) -> list[EtfListing]:
    """Parse the listing page HTML and return one EtfListing per table row, sorted by ticker.

    Rows that cannot be parsed are logged and skipped; duplicates are dropped.
    Raises ListingParseError if the table itself is not found.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one(TABLE_SELECTOR)
    if table is None:
        raise ListingParseError(f"ETF table not found ({TABLE_SELECTOR})")

    etfs: list[EtfListing] = []
    seen: set[str] = set()
    for index, row in enumerate(table.select("tbody tr"), start=1):
        link = row.select_one(TICKER_SELECTOR)
        name_cell = row.select_one(NAME_SELECTOR)
        if link is None or not link.get("href"):
            logger.warning("Listing row %d: ticker link not found, row skipped", index)
            continue

        ticker = link.get_text(strip=True).upper()
        url = urljoin(base_url, link["href"])
        name = _clean_name(name_cell) if name_cell else ""

        if not TICKER_PATTERN.match(ticker):
            logger.warning("Listing row %d: unexpected ticker format %r", index, ticker)
        if not urlparse(url).path.startswith("/etfs/"):
            logger.warning("Listing row %d (%s): unexpected URL %s", index, ticker, url)
        if not name:
            logger.warning("Listing row %d (%s): fund name not found", index, ticker)
        if ticker in seen:
            logger.warning("Listing row %d: duplicate ticker %s, row skipped", index, ticker)
            continue

        seen.add(ticker)
        etfs.append(EtfListing(ticker=ticker, name=name, url=url))

    etfs.sort(key=lambda etf: etf.ticker)
    logger.info("Listing parsed: %d ETFs", len(etfs))
    return etfs


def _clean_name(cell) -> str:
    """Fund name without footnote markers (the site appends them in <sup> tags)."""
    for sup in cell.select("sup"):
        sup.decompose()
    return " ".join(cell.get_text(" ", strip=True).split())

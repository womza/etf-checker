"""Per-ETF result line shown in the terminal and written to the log.

Format (docs/requirements/REQ-001-etf-result-line.md), fixed-width columns so the
separators line up across ETFs:
    ✗ AGGH     NAV: MISSING  |  Price: MISSING  |  Duration:    7.40  |  Holdings: 17 rows [as of 10/30/2026]
    ✓ SPYC     NAV:  $44.27  |  Price:  $44.28  |  Duration:       -  |  Holdings: 23 rows [as of 10/30/2026]
"""

import sys
from decimal import Decimal

from scraper.details import EtfDetails
from validators import EtfValidation

OK_SYMBOL = "✓"
ERROR_SYMBOL = "✗"
ASCII_SYMBOLS = {OK_SYMBOL: "OK", ERROR_SYMBOL: "X "}  # same width keeps columns aligned

TICKER_WIDTH = 8
# Width of "MISSING", which also fits "$100.09" and "-28.53". Longer values
# (e.g. "$1000.00") are shown in full and only that line shifts.
VALUE_WIDTH = 7
SEPARATOR = "  |  "
MISSING = "MISSING"
NOT_APPLICABLE = "-"


def format_result_line(ticker: str, details: EtfDetails | None, validation: EtfValidation) -> str:
    """Build the result line. `details` is None when the page could not be used.

    The symbol comes from the validation (✗ if any field is MISSING or INCORRECT).
    """
    details = details or EtfDetails()

    if not details.duration_published:
        duration = NOT_APPLICABLE
    elif details.duration is None:
        duration = MISSING
    else:
        duration = f"{details.duration:.2f}"

    if details.holdings_rows is None:
        holdings = MISSING
    else:
        noun = "row" if details.holdings_rows == 1 else "rows"
        holdings = f"{details.holdings_rows} {noun} [as of {details.holdings_date or MISSING}]"

    symbol = OK_SYMBOL if validation.ok else ERROR_SYMBOL
    fields = SEPARATOR.join(
        [
            f"NAV: {_money(details.nav):>{VALUE_WIDTH}}",
            f"Price: {_money(details.price):>{VALUE_WIDTH}}",
            f"Duration: {duration:>{VALUE_WIDTH}}",
            f"Holdings: {holdings}",
        ]
    )
    return f"{symbol} {ticker.upper():<{TICKER_WIDTH}} {fields}"


def to_terminal(line: str, stream=None) -> str:
    """Replace ✓/✗ with OK/X if the terminal cannot encode them."""
    encoding = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        line.encode(encoding)
        return line
    except (UnicodeEncodeError, LookupError):
        for symbol, fallback in ASCII_SYMBOLS.items():
            line = line.replace(symbol, fallback)
        return line.encode(encoding, errors="replace").decode(encoding)


def _money(value: Decimal | None) -> str:
    return MISSING if value is None else f"${value:.2f}"

"""Tests: extraction (Phase 4), REQ-001 result line, REQ-002 validations, reports (Phase 6).

Run: python -m unittest discover -s tests -v
"""

import csv
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from decimal import Decimal

from datetime import date

from reporting import EtfRecord, write_csv, write_json
from scraper.details import EtfDetails, parse_details
from utils.result_line import format_result_line, to_terminal
from validators import Status, validate_etf

RUN_DATE = date(2026, 11, 2)  # Monday; site data as of Friday 10/30/2026

# REQ-001 reference line with fixed-width (aligned) value columns
REFERENCE_LINE = (
    "✗ AGGH     NAV: MISSING  |  Price: MISSING  |  Duration:    7.40  |  "
    "Holdings: 17 rows [as of 10/30/2026]"
)


def result_line(ticker, details):
    return format_result_line(ticker, details, validate_etf(details, RUN_DATE))


def overview_row(label: str, value: str) -> str:
    return (
        '<div class="c-fund-overview__row">'
        f'<div class="c-fund-overview__cell-header">{label}</div>'
        f'<div class="c-fund-overview__cell-data">{value}</div></div>'
    )


def make_page(
    ticker="AGGH",
    nav="$19.21",
    price="$19.27",
    duration: str | None = "7.40",
    rows: int | None = 17,
    holdings_date: str | None = "As of 10/30/2026",
    pane: bool = True,
    premium: str | None = "0.33%",
    as_of: str = "10/30/2026",
) -> str:
    overview = overview_row("Ticker Symbol", ticker)
    overview += overview_row(f"NAV Per Share as of {as_of}", nav)
    overview += overview_row(f"Market Price as of {as_of}", price)
    if premium is not None:
        overview += overview_row(f"Premium/Discount (%) as of {as_of}", premium)
    if duration is not None:
        overview += overview_row("Portfolio Duration", duration)
    holdings = ""
    if pane:
        date_html = f'<p class="o-etfs__date mb-0">{holdings_date}</p>' if holdings_date else ""
        table = ""
        if rows is not None:
            body = "".join("<tr><td>X</td><td>Name</td><td>1</td><td>1%</td></tr>" for _ in range(rows))
            table = f"<table><thead><tr><th>Ticker</th></tr></thead><tbody>{body}</tbody></table>"
        holdings = f'<div id="holdings-table-pane">{date_html}{table}</div>'
    return f"<html><body>{overview}{holdings}</body></html>"


class ParseDetailsTest(unittest.TestCase):
    def test_full_page(self):
        d = parse_details(make_page())
        self.assertEqual(d.page_ticker, "AGGH")
        self.assertEqual(d.nav, Decimal("19.21"))
        self.assertEqual(d.nav_date, "10/30/2026")
        self.assertEqual(d.price, Decimal("19.27"))
        self.assertEqual(d.duration, Decimal("7.40"))
        self.assertEqual(d.holdings_rows, 17)
        self.assertEqual(d.holdings_date, "10/30/2026")
        self.assertEqual(d.issues, [])

    def test_na_values_are_missing(self):
        d = parse_details(make_page(nav="N/A", price="N/A"))
        self.assertIsNone(d.nav)
        self.assertIsNone(d.price)
        self.assertEqual(len(d.issues), 2)

    def test_duration_not_published(self):
        d = parse_details(make_page(duration=None))
        self.assertFalse(d.duration_published)
        self.assertEqual(d.issues, [])

    def test_negative_duration_and_thousands(self):
        d = parse_details(make_page(duration="-28.53", nav="$1,000.09"))
        self.assertEqual(d.duration, Decimal("-28.53"))
        self.assertEqual(d.nav, Decimal("1000.09"))

    def test_no_holdings_table(self):
        d = parse_details(make_page(rows=None))
        self.assertIsNone(d.holdings_rows)
        self.assertIn("Holdings: no table on page", d.issues)

    def test_date_kept_as_shown(self):
        d = parse_details(make_page(holdings_date="As of Oct 30, 2026"))
        self.assertEqual(d.holdings_date, "Oct 30, 2026")


class ResultLineTest(unittest.TestCase):
    def line(self, ticker="AGGH", **page):
        line = result_line(ticker, parse_details(make_page(ticker=ticker, **page)))
        return line.startswith("✓"), line

    def test_reference_line(self):
        ok, line = self.line(nav="N/A", price="N/A")
        self.assertFalse(ok)
        self.assertEqual(line, REFERENCE_LINE)

    def test_ok_line(self):
        ok, line = self.line()
        self.assertTrue(ok)
        self.assertEqual(
            line,
            "✓ AGGH     NAV:  $19.21  |  Price:  $19.27  |  Duration:    7.40  |  "
            "Holdings: 17 rows [as of 10/30/2026]",
        )

    def test_pipes_aligned(self):
        variants = [
            self.line(ticker="AGGH")[1],
            self.line(ticker="XV", duration=None)[1],
            self.line(ticker="PFIX", duration="-28.53", nav="$56.77", price="$55.87", premium="-1.59% *")[1],
            self.line(ticker="SBIL", nav="$100.09", price="$100.08", premium="-0.01%", duration=None)[1],
            self.line(ticker="XYZ", nav="N/A", price="N/A")[1],
            result_line("ERR", None),
        ]
        pipes = {tuple(i for i, ch in enumerate(line) if ch == "|") for line in variants}
        self.assertEqual(len(pipes), 1, "\n".join(variants))

    def test_no_duration_is_ok(self):
        ok, line = self.line(duration=None)
        self.assertTrue(ok)
        self.assertIn("Duration:       -  |", line)

    def test_negative_duration_is_ok(self):
        ok, line = self.line(duration="-28.53")
        self.assertTrue(ok)
        self.assertIn("Duration:  -28.53  |", line)

    def test_singular_row(self):
        _, line = self.line(rows=1)
        self.assertIn("Holdings: 1 row [as of", line)

    def test_missing_holdings_date(self):
        ok, line = self.line(holdings_date=None)
        self.assertFalse(ok)
        self.assertIn("17 rows [as of MISSING]", line)

    def test_missing_holdings(self):
        ok, line = self.line(rows=None)
        self.assertFalse(ok)
        self.assertTrue(line.endswith("Holdings: MISSING"))

    def test_page_error(self):
        line = result_line("XYZ", None)
        self.assertEqual(
            line,
            "✗ XYZ      NAV: MISSING  |  Price: MISSING  |  Duration:       -  |  Holdings: MISSING",
        )

    def test_ascii_fallback(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        self.assertTrue(to_terminal(REFERENCE_LINE, stream).startswith("X  AGGH"))
        utf8 = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        self.assertEqual(to_terminal(REFERENCE_LINE, utf8), REFERENCE_LINE)

    def test_empty_details(self):
        self.assertTrue(result_line("AGGH", EtfDetails()).startswith("✗"))


class ValidationTest(unittest.TestCase):
    def validate(self, run_date=RUN_DATE, **page):
        return validate_etf(parse_details(make_page(**page)), run_date)

    def test_all_verified(self):
        v = self.validate()
        self.assertEqual(v.nav.status, Status.VERIFIED)
        self.assertEqual(v.price.status, Status.VERIFIED)
        self.assertEqual(v.holdings.status, Status.VERIFIED)
        self.assertEqual(v.duration.status, Status.NOT_VERIFIABLE)
        self.assertTrue(v.ok)

    def test_duration_not_applicable(self):
        v = self.validate(duration=None)
        self.assertEqual(v.duration.status, Status.NOT_APPLICABLE)
        self.assertTrue(v.ok)

    def test_duration_unreadable_is_missing(self):
        v = self.validate(duration="abc")
        self.assertEqual(v.duration.status, Status.MISSING)
        self.assertFalse(v.ok)

    def test_na_is_missing(self):
        v = self.validate(nav="N/A")
        self.assertEqual(v.nav.status, Status.MISSING)
        self.assertEqual(v.price.status, Status.NOT_VERIFIABLE)  # cross-check impossible
        self.assertFalse(v.ok)

    def test_premium_mismatch_is_incorrect(self):
        v = self.validate(premium="1.50%")
        self.assertEqual(v.nav.status, Status.INCORRECT)
        self.assertEqual(v.price.status, Status.INCORRECT)
        self.assertFalse(v.ok)

    def test_premium_within_rounding_is_verified(self):
        # Real case TYA 10/30/2026: computed 0.427%, site 0.39%
        v = self.validate(nav="$11.71", price="$11.76", premium="0.39%")
        self.assertEqual(v.nav.status, Status.VERIFIED)

    def test_premium_absent_is_not_verifiable(self):
        v = self.validate(premium=None)
        self.assertEqual(v.nav.status, Status.NOT_VERIFIABLE)
        self.assertTrue(v.ok)

    def test_not_positive_price(self):
        v = self.validate(price="$0.00")
        self.assertEqual(v.price.status, Status.INCORRECT)

    def test_stale_dates(self):
        v = self.validate(run_date=date(2026, 11, 6))  # Friday: 5 business days after 10/30
        self.assertEqual(v.nav.status, Status.INCORRECT)
        self.assertEqual(v.holdings.status, Status.INCORRECT)
        self.assertFalse(v.ok)

    def test_weekend_is_not_stale(self):
        v = self.validate(run_date=date(2026, 11, 4))  # Wednesday: 3 business days
        self.assertTrue(v.ok)

    def test_future_date(self):
        v = self.validate(as_of="11/05/2026", holdings_date="As of 11/05/2026")
        self.assertEqual(v.nav.status, Status.INCORRECT)
        self.assertEqual(v.holdings.status, Status.INCORRECT)

    def test_unknown_date_format_is_not_verifiable(self):
        v = self.validate(holdings_date="As of Oct 30, 2026")
        self.assertEqual(v.holdings.status, Status.NOT_VERIFIABLE)
        self.assertTrue(v.ok)

    def test_empty_holdings_table(self):
        v = self.validate(rows=0)
        self.assertEqual(v.holdings.status, Status.INCORRECT)

    def test_missing_holdings_date(self):
        v = self.validate(holdings_date=None)
        self.assertEqual(v.holdings.status, Status.MISSING)

    def test_page_error(self):
        v = validate_etf(None, RUN_DATE)
        self.assertEqual(v.nav.status, Status.MISSING)
        self.assertEqual(v.duration.status, Status.NOT_APPLICABLE)
        self.assertFalse(v.ok)


class ReportTest(unittest.TestCase):
    RUN = datetime(2026, 11, 2, 20, 0, 0)

    def records(self):
        ok = parse_details(make_page())
        no_duration = parse_details(make_page(ticker="SPYC", duration=None, nav="N/A"))
        return [
            EtfRecord("AGGH", "Simplify Aggregate Bond ETF", "https://x/aggh", ok, validate_etf(ok, RUN_DATE)),
            EtfRecord("SPYC", "Simplify US Equity", "https://x/spyc", no_duration,
                      validate_etf(no_duration, RUN_DATE)),
            EtfRecord("XYZ", "Broken", "https://x/xyz", None, validate_etf(None, RUN_DATE),
                      page_error="detail page failed: ConnectionError"),
        ]

    def test_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_csv(Path(tmp) / "r.csv", self.records(), self.RUN)
            with path.open(encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 3)
        aggh, spyc, xyz = rows
        self.assertEqual(aggh["nav"], "19.21")
        self.assertEqual(aggh["duration"], "7.40")
        self.assertEqual(aggh["holdings_rows"], "17")
        self.assertEqual(aggh["result"], "OK")
        self.assertEqual(spyc["duration"], "")  # not applicable -> empty cell
        self.assertEqual(spyc["duration_status"], "NOT_APPLICABLE")
        self.assertEqual(spyc["nav"], "")
        self.assertEqual(spyc["nav_status"], "MISSING")
        self.assertEqual(spyc["result"], "ERROR")
        self.assertIn("ConnectionError", xyz["issues"])

    def test_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_json(Path(tmp) / "r.json", self.records(), self.RUN, "https://src", 39, 3)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["summary"]["etfs_found"], 39)
        self.assertEqual(data["summary"]["etfs_checked"], 3)
        self.assertEqual(data["summary"]["ok"], 1)
        self.assertEqual(data["summary"]["statuses"]["Duration"]["NOT_APPLICABLE"], 2)
        aggh, spyc, xyz = data["etfs"]
        self.assertEqual(aggh["nav"]["value"], 19.21)
        self.assertEqual(aggh["nav"]["raw"], "$19.21")
        self.assertEqual(aggh["duration"]["value"], 7.4)
        self.assertIsNone(spyc["duration"]["value"])  # not applicable -> null
        self.assertIsNone(spyc["nav"]["value"])
        self.assertEqual(xyz["page_error"], "detail page failed: ConnectionError")


if __name__ == "__main__":
    unittest.main()

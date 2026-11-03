"""Simplify ETF Checker: entry point.

Usage:
    python etf_checker.py [--limit N]

Current status: Phase 6. Extracts the ETF list and, for every ETF, NAV,
Market Price, Portfolio Duration and the holdings row count with its date,
then validates them (docs/requirements/REQ-002). One result line per ETF is
printed (docs/requirements/REQ-001).

The .log / .csv / .json files are currently disabled: see the TODO in main().
"""

import argparse
import logging
import sys
from collections import Counter
from datetime import date, datetime

import requests

import config
from scraper.details import parse_details
from scraper.http_client import HttpClient
from scraper.listing import EtfListing, ListingParseError, parse_listing
from utils.logger import FILE_ONLY, run_stamp, setup_logger
from utils.result_line import format_result_line, to_terminal
from reporting import EtfRecord
# from reporting import write_csv, write_json  # TODO: uncomment to enable CSV/JSON reports (see main)
from validators import Status, validate_etf

LINE = "=" * 56
THIN_LINE = "-" * 56
TITLE = "SIMPLIFY ETF CHECKER"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Simplify ETF data.")
    parser.add_argument(
        "--limit", type=int, default=None, help="only check the first N ETFs (for quick tests)"
    )
    return parser.parse_args()


def check_etf(client: HttpClient, etf: EtfListing, run_date: date, log) -> tuple[EtfRecord, str]:
    """Load one detail page, extract and validate its data; return (record, result line).

    Technical detail goes to the log file only; the result line is the only
    terminal output per ETF.
    """
    details = None
    page_error = None
    try:
        response = client.get(etf.url)
    except requests.RequestException as exc:
        page_error = f"detail page failed: {exc.__class__.__name__}"
        log.warning("%s: detail page failed (%s): %s", etf.ticker, etf.url, exc, extra=FILE_ONLY)
    else:
        parsed = parse_details(response.text)
        if parsed.page_ticker is None:
            page_error = "'Ticker Symbol' not found on page"
            log.warning("%s: 'Ticker Symbol' not found on %s", etf.ticker, etf.url, extra=FILE_ONLY)
        elif parsed.page_ticker != etf.ticker:
            page_error = f"page shows ticker {parsed.page_ticker}, data ignored"
            log.warning(
                "%s: page shows ticker %s (%s), data ignored",
                etf.ticker, parsed.page_ticker, etf.url, extra=FILE_ONLY,
            )
        else:
            details = parsed
            log.info(
                "%s: url=%s | NAV raw=%r as of %s | Price raw=%r as of %s | "
                "Duration raw=%r | Holdings rows=%s as of %s",
                etf.ticker, etf.url, parsed.nav_raw, parsed.nav_date,
                parsed.price_raw, parsed.price_date, parsed.duration_raw,
                parsed.holdings_rows, parsed.holdings_date, extra=FILE_ONLY,
            )
            log.info(
                "%s: Premium/Discount raw=%r as of %s",
                etf.ticker, parsed.premium_raw, parsed.premium_date, extra=FILE_ONLY,
            )
            for issue in parsed.issues:
                log.warning("%s: %s", etf.ticker, issue, extra=FILE_ONLY)

    validation = validate_etf(details, run_date)
    for name, result in validation.fields().items():
        level = logging.WARNING if result.is_error else logging.INFO
        reasons = f" ({'; '.join(result.reasons)})" if result.reasons else ""
        log.log(level, "%s: %s %s%s", etf.ticker, name, result.status.value, reasons, extra=FILE_ONLY)

    line = format_result_line(etf.ticker, details, validation)
    log.log(logging.INFO if validation.ok else logging.WARNING, line, extra=FILE_ONLY)
    record = EtfRecord(etf.ticker, etf.name, etf.url, details, validation, page_error)
    return record, line


def main() -> int:
    args = parse_args()
    run_date = datetime.now()
    stamp = run_stamp(run_date)
    # TODO: Reports are disabled. To enable/disable the files written to reports/
    #   - .log  : swap the two `log_path` lines below
    #   - .csv / .json : uncomment the "Write reports" block at the end of main()
    #                    and the `write_csv, write_json` import at the top
    # log_path = config.REPORTS_DIR / f"etf_checker_{stamp}.log"  # .log enabled
    log_path = None  # .log disabled
    log = setup_logger(log_path, config.LOG_LEVEL)
    log.info("Run started (stamp=%s, limit=%s)", stamp, args.limit)

    print(LINE)
    print(TITLE.center(len(LINE)))
    print(LINE)
    print()
    print(f"Run Date: {run_date:%Y-%m-%d %H:%M:%S}")
    print()
    if not config.BASE_URL:
        log.error("BASE_URL is not set")
        print("[ERROR] BASE_URL is not set. Copy .env.example to .env and set BASE_URL.")
        return 1

    print("Fetching ETF listing page...")

    exit_code = 0
    with HttpClient() as client:
        try:
            response = client.get(config.LISTING_URL)
            etfs = parse_listing(response.text)
        except (requests.RequestException, ListingParseError) as exc:
            log.error("Listing page failed: %s", exc)
            print(f"[ERROR] Listing page: {exc}")
            etfs = []
            exit_code = 1

        print()
        print("ETF Listing Table")
        print(f"Found: {len(etfs)} ETFs")

        selected = etfs[: args.limit] if args.limit else etfs
        ok_count = 0
        status_counts: dict[str, Counter] = {}
        records: list[EtfRecord] = []
        if selected:
            print()
            print(THIN_LINE)
            print(f"Checking ETFs ({len(selected)})...")
            print(THIN_LINE)
            print()
            for etf in selected:
                record, line = check_etf(client, etf, run_date.date(), log)
                records.append(record)
                ok_count += record.validation.ok
                for name, result in record.validation.fields().items():
                    status_counts.setdefault(name, Counter())[result.status] += 1
                print(to_terminal(line), flush=True)

        print()
        print(THIN_LINE)
        print("SUMMARY")
        print(THIN_LINE)
        print()
        print(f"{'ETFs found:':<22}{len(etfs)}")
        print(f"{'ETFs checked:':<22}{len(selected)}")
        print(f"{'OK:':<22}{ok_count}")
        print(f"{'With errors:':<22}{len(selected) - ok_count}")
        if status_counts:
            print()
            print(f"{'Field':<10}" + "".join(f"{status.value:>16}" for status in Status))
            for name, counts in status_counts.items():
                print(f"{name:<10}" + "".join(f"{counts[status]:>16}" for status in Status))
        if ok_count < len(selected):
            exit_code = 1

    saved = [log_path] if log_path else []
    # --- Write reports (TODO: uncomment this block to enable the .csv / .json files) ---
    # try:
    #     saved.append(write_csv(config.REPORTS_DIR / f"etf_report_{stamp}.csv", records, run_date))
    #     saved.append(
    #         write_json(
    #             config.REPORTS_DIR / f"etf_report_{stamp}.json",
    #             records,
    #             run_date,
    #             source_url=config.LISTING_URL,
    #             etfs_found=len(etfs),
    #             max_data_age=config.MAX_DATA_AGE_BUSINESS_DAYS,
    #         )
    #     )
    #     log.info("Reports saved: %s", ", ".join(str(path) for path in saved))
    # except OSError as exc:
    #     log.error("Could not write reports: %s", exc)
    #     print(f"[ERROR] Could not write reports: {exc}")
    #     exit_code = 1

    if saved:
        print()
        print("Files saved:")
        for path in saved:
            shown = path.relative_to(config.PROJECT_ROOT) if path.is_relative_to(config.PROJECT_ROOT) else path
            print(f"  {shown}")
    print(LINE)
    log.info("Run finished (exit_code=%s)", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

"""CSV and JSON reports of a run.

Missing data rules (README):
- Values that are not available are written as an empty CSV cell / JSON null,
  never as a placeholder number. The `*_status` column says why.
- Numbers are written without "$" or "%", with the precision shown on the site.
"""

import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from scraper.details import EtfDetails
from validators import EtfValidation, FieldResult, Status

CSV_COLUMNS = [
    "run_date",
    "ticker",
    "name",
    "url",
    "result",
    "nav",
    "nav_date",
    "nav_status",
    "price",
    "price_date",
    "price_status",
    "premium_discount_pct",
    "premium_discount_date",
    "duration",
    "duration_status",
    "holdings_rows",
    "holdings_date",
    "holdings_status",
    "issues",
]


@dataclass
class EtfRecord:
    """Everything known about one checked ETF."""

    ticker: str
    name: str
    url: str
    details: EtfDetails | None  # None when the page failed or belongs to another ticker
    validation: EtfValidation
    page_error: str | None = None

    @property
    def result(self) -> str:
        return "OK" if self.validation.ok else "ERROR"

    def issues(self) -> list[str]:
        """Page error, extraction issues and validation reasons, in that order."""
        issues = [self.page_error] if self.page_error else []
        if self.details:
            issues += self.details.issues
        for name, field_result in self.validation.fields().items():
            if field_result.status != Status.VERIFIED:
                issues += [f"{name}: {reason}" for reason in field_result.reasons]
        return list(dict.fromkeys(issues))  # drop duplicates, keep order


def write_csv(path: Path, records: list[EtfRecord], run_date: datetime) -> Path:
    """One row per ETF. UTF-8 with BOM so Excel opens it with the right encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record in records:
            d = record.details or EtfDetails()
            v = record.validation
            writer.writerow(
                {
                    "run_date": f"{run_date:%Y-%m-%d %H:%M:%S}",
                    "ticker": record.ticker,
                    "name": record.name,
                    "url": record.url,
                    "result": record.result,
                    "nav": _cell(d.nav),
                    "nav_date": _cell(d.nav_date),
                    "nav_status": v.nav.status.value,
                    "price": _cell(d.price),
                    "price_date": _cell(d.price_date),
                    "price_status": v.price.status.value,
                    "premium_discount_pct": _cell(d.premium_discount),
                    "premium_discount_date": _cell(d.premium_date),
                    "duration": _cell(d.duration),
                    "duration_status": v.duration.status.value,
                    "holdings_rows": _cell(d.holdings_rows),
                    "holdings_date": _cell(d.holdings_date),
                    "holdings_status": v.holdings.status.value,
                    "issues": "; ".join(record.issues()),
                }
            )
    return path


def write_json(
    path: Path,
    records: list[EtfRecord],
    run_date: datetime,
    source_url: str,
    etfs_found: int,
    max_data_age: int,
) -> Path:
    """Full run report: metadata, summary counts and one object per ETF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "run_date": run_date.isoformat(timespec="seconds"),
        "source": source_url,
        "settings": {"max_data_age_business_days": max_data_age},
        "summary": _summary(records, etfs_found),
        "etfs": [_record_json(record) for record in records],
    }
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _summary(records: list[EtfRecord], etfs_found: int) -> dict:
    by_field: dict[str, Counter] = {}
    for record in records:
        for name, field_result in record.validation.fields().items():
            by_field.setdefault(name, Counter())[field_result.status.value] += 1
    ok = sum(record.validation.ok for record in records)
    return {
        "etfs_found": etfs_found,
        "etfs_checked": len(records),
        "ok": ok,
        "with_errors": len(records) - ok,
        "statuses": {
            name: {status.value: counts[status.value] for status in Status}
            for name, counts in by_field.items()
        },
    }


def _record_json(record: EtfRecord) -> dict:
    d = record.details or EtfDetails()
    v = record.validation
    return {
        "ticker": record.ticker,
        "name": record.name,
        "url": record.url,
        "result": record.result,
        "page_error": record.page_error,
        "nav": {"value": _num(d.nav), "raw": d.nav_raw, "date": d.nav_date, **_status(v.nav)},
        "price": {"value": _num(d.price), "raw": d.price_raw, "date": d.price_date, **_status(v.price)},
        "premium_discount_pct": {
            "value": _num(d.premium_discount),
            "raw": d.premium_raw,
            "date": d.premium_date,
        },
        "duration": {"value": _num(d.duration), "raw": d.duration_raw, **_status(v.duration)},
        "holdings": {"rows": d.holdings_rows, "date": d.holdings_date, **_status(v.holdings)},
        "extraction_issues": list(d.issues),
    }


def _status(field_result: FieldResult) -> dict:
    return {"status": field_result.status.value, "reasons": list(field_result.reasons)}


def _cell(value) -> str:
    return "" if value is None else str(value)


def _num(value: Decimal | None) -> float | None:
    # Site values have at most a few decimals, so float keeps them exactly as shown
    return None if value is None else float(value)

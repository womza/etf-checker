# ETF Checker

Python CLI tool that checks and validates, on a daily basis, the information of the ETFs published
on the provider's ETF listing page (configured via `BASE_URL`): NAV, Market Price, Portfolio Duration, holdings count and update dates.

## Extracted data

| Group | Fields |
|---|---|
| General | Ticker, full fund name, detail page URL, run date |
| Financial | NAV, Market Price, Portfolio Duration |
| Holdings | **Total number of rows in the holdings table** and holdings "as of" date (individual holdings are not read) |
| Dates | NAV date, Market Price date, holdings date, other relevant dates on the page |

Missing fields are reported as missing; values are never invented.

### Missing data rules

| Situation on the website | Extracted value | Status |
|---|---|---|
| NAV shows `N/A` (no price published) | none | `MISSING` (terminal: `NAV: MISSING`; reason in the log) |
| Market Price shows `N/A` (no price published) | none | `MISSING` (terminal: `Price: MISSING`; reason in the log) |
| Holdings table not rendered (site-side error) | none | `MISSING` (terminal: `Holdings: MISSING`; reason in the log) |
| Portfolio Duration not published (non fixed-income ETF) | none | Not applicable, not an error (terminal: `Duration: -`; CSV: empty cell; JSON: `null`) |

## Terminal and log output

One line per ETF, identical in the terminal and in the log ([REQ-001](docs/requirements/REQ-001-etf-result-line.md)):

```
✓ AGGH     NAV:  $19.21  |  Price:  $19.27  |  Duration:    7.40  |  Holdings: 17 rows [as of 10/30/2026]
✓ SPYC     NAV:  $44.27  |  Price:  $44.28  |  Duration:       -  |  Holdings: 23 rows [as of 10/30/2026]
✗ AGGH     NAV: MISSING  |  Price: MISSING  |  Duration:    7.40  |  Holdings: 17 rows [as of 10/30/2026]
```

Value columns are fixed-width so the `|` separators line up. `✗` means at least one field is `MISSING` or `INCORRECT` (see [Validation statuses](#validation-statuses)). `Duration: -` (not published) is not an error.

`N/A` published by the site is recognized explicitly and is never treated as a parsing error or as an incorrect value.

## Extraction strategy

Findings from the research phase (Phase 1):

- The site is Drupal 10 with server-side rendering. **All required data is present in the initial HTML.**
- **requests + BeautifulSoup** are used. **Playwright is not needed**: the site's JavaScript only renders charts.
- There is no public JSON API for this data.
- No external reference sources are used for now. Validation is structural and internal-consistency based;
  the architecture is prepared to plug in external reference sources later.

## Requirements

- Python 3.13+ (managed with [uv](https://docs.astral.sh/uv/))
- Internet connection

## Installation

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

cd etf-checker
uv python install 3.13
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Configuration

A `.env` file is required: the provider website URL is not stored in the repository and must be set in `BASE_URL`.

```bash
cp .env.example .env
# then edit .env and set BASE_URL
```

| Variable | Default | Description |
|---|---|---|
| `BASE_URL` | (none, required) | Base URL of the ETF provider website, without trailing slash |
| `REQUEST_TIMEOUT` | 20 | Maximum seconds per request |
| `REQUEST_DELAY` | 1.5 | Minimum pause between requests |
| `MAX_RETRIES` | 3 | Retries on network errors or HTTP 429/5xx |
| `REPORTS_DIR` | reports | Reports and logs folder |
| `LOG_LEVEL` | INFO | File log level |
| `MAX_DATA_AGE_BUSINESS_DAYS` | 3 | Max age of NAV/Price/holdings dates before they count as stale |

## Usage

One command, no need to activate the virtual environment:

```bash
./run.sh              # check all ETFs
./run.sh --limit 5    # check only the first 5 ETFs (quick test)
./run.sh test         # unit tests
```

### Output files (currently disabled)

The `.log`, `.csv` and `.json` files are **disabled**: results are only shown in the terminal.
To enable them, follow the `TODO` in `main()` of `etf_checker.py` (uncomment the `log_path`
line for the `.log`, and the "Write reports" block plus the `write_csv, write_json` import for
the `.csv` / `.json`). When enabled, each run writes files with date and time in the name, so
previous runs are never overwritten:

- `reports/etf_checker_YYYY-MM-DD_HHMMSS.log`: technical log
- `reports/etf_report_YYYY-MM-DD_HHMMSS.csv`: one row per ETF (UTF-8 with BOM, opens directly in Excel)
- `reports/etf_report_YYYY-MM-DD_HHMMSS.json`: run metadata, summary counts and full detail per ETF

The exit code is `0` when every ETF is `✓`, `1` otherwise (useful for scheduled runs).

### Reports

CSV columns: `run_date, ticker, name, url, result (OK/ERROR), nav, nav_date, nav_status, price, price_date,
price_status, premium_discount_pct, premium_discount_date, duration, duration_status, holdings_rows,
holdings_date, holdings_status, issues`.

- Numbers are written without `$` or `%`, as shown on the site (e.g. `19.21`, `-28.53`).
- Values that are not available are an **empty cell** (CSV) or **`null`** (JSON); the `*_status` column says why.
- `issues` joins the page error, extraction problems and validation reasons.
- The JSON also keeps the raw text read from the page (`raw`) and the reasons per field.

## Project structure

```
etf-checker/
├── run.sh                  # One-command launcher
├── etf_checker.py          # Entry point
├── config.py               # Settings (URLs, timeouts, delays, paths)
├── scraper/
│   ├── http_client.py      # HTTP session: timeouts, retries, delays
│   ├── listing.py          # ETF list (ticker, name, URL)
│   └── details.py          # Per-ETF data: NAV, price, duration, holdings
├── validators/             # Independent validations (REQ-002)
│   ├── common.py           # Statuses, date rules
│   ├── consistency.py      # NAV / Price / Premium-Discount cross-check
│   ├── nav.py
│   ├── price.py
│   ├── duration.py
│   └── holdings.py
├── reporting/
│   └── report.py           # CSV and JSON reports
├── utils/
│   ├── logger.py           # Execution log
│   └── result_line.py      # Per-ETF result line (REQ-001)
├── tests/                  # Unit tests (unittest)
├── docs/requirements/      # Requirements
└── reports/                # Generated output (git-ignored)
```

## Validation statuses

| Status | Meaning |
|---|---|
| `VERIFIED` | Value found and passed all available validations |
| `INCORRECT` | Value found but fails a validation rule |
| `MISSING` | Value could not be extracted |
| `NOT_VERIFIABLE` | Value extracted, but there is not enough information to confirm it |
| `NOT_APPLICABLE` | Portfolio Duration not published (non fixed-income ETF); not an error |

Rules ([REQ-002](docs/requirements/REQ-002-validations.md)):

- **NAV / Market Price**: present, > 0, date not in the future and not older than `MAX_DATA_AGE_BUSINESS_DAYS`, and consistent with the published Premium/Discount (%) within the site's rounding.
- **Portfolio Duration**: any sign accepted; `NOT_VERIFIABLE` (no reference source) or `NOT_APPLICABLE`.
- **Holdings**: table and "As of" date present, at least one row, date fresh.

`VERIFIED`, `NOT_VERIFIABLE` and `NOT_APPLICABLE` show `✓`; `INCORRECT` and `MISSING` show `✗`. Reasons are in the log.

## Known limitations

- **Portfolio Duration** is only published for fixed-income ETFs (13 of 39). For the rest it is "not applicable", not an error.
- **Negative durations are valid** (e.g. PFIX). No fixed ranges are used.
- Data reflects the previous business day's close.
- Extraction relies on text labels on the site (e.g. "NAV Per Share as of"). If they change, fields will show as `MISSING` and be logged.

## Progress

- [x] Phase 1: Research
- [x] Phase 2: Initial structure
- [x] Phase 3: ETF list extraction
- [x] Phase 4: Data extraction
- [x] Phase 5: Validations
- [x] Phase 6: Reports

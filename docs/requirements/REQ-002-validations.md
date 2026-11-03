# REQ-002: Field validations (Phase 5)

| | |
|---|---|
| Status | Implemented (Phase 5), pending user review |
| Date | 2026-11-02 |
| Code | `validators/` |

## 1. Principles

- Validation is **independent from extraction**: validators only read `EtfDetails`.
- Only information published on the Simplify site is used (no external sources yet).
- **No fixed value ranges** (e.g. negative durations are valid). Tolerances come from
  the rounding the site applies, not from arbitrary margins.
- Every non-`VERIFIED` status carries a reason, written to the log.

## 2. Statuses

| Status | Meaning | Symbol |
|---|---|---|
| `VERIFIED` | Value found and passed all available validations | `✓` |
| `NOT_VERIFIABLE` | Value found, but there is not enough information to confirm it | `✓` |
| `NOT_APPLICABLE` | Field not published and not expected (Portfolio Duration of non fixed-income ETFs) | `✓` |
| `INCORRECT` | Value found but fails a validation rule | `✗` |
| `MISSING` | Value could not be extracted | `✗` |

When several rules apply, the most severe wins: `INCORRECT` > `NOT_VERIFIABLE` > `VERIFIED`.

## 3. Shared date rules (NAV, Market Price, holdings)

| Situation | Result |
|---|---|
| Date not found on the page | `NOT_VERIFIABLE` |
| Date not in `MM/DD/YYYY` format (can't be compared) | `NOT_VERIFIABLE` |
| Date later than the run date | `INCORRECT` (future date) |
| Older than `MAX_DATA_AGE_BUSINESS_DAYS` business days (default 3, weekends excluded, no holiday calendar) | `INCORRECT` (stale) |

The default of 3 allows for the site showing the previous close plus a market holiday.

## 4. NAV and Market Price

| # | Rule | Result if it fails |
|---|---|---|
| 1 | Value present (not `N/A`, readable) | `MISSING` |
| 2 | Value > 0 | `INCORRECT` |
| 3 | Date rules (section 3) | see section 3 |
| 4 | Cross-check with the published Premium/Discount (%) (section 5) | `INCORRECT` on mismatch; `NOT_VERIFIABLE` if it cannot be done |

## 5. Premium/Discount cross-check

`Premium/Discount (%) = (Market Price − NAV) / NAV × 100`

- NAV and Price are shown rounded to cents, the percentage to 2 decimals. The check passes when
  the published percentage can be produced by some NAV and price within ±$0.005 of the shown
  values, ±0.005 percentage points for the percentage rounding.
- Run on 2026-11-02 (data as of 10/30/2026): all 39 ETFs pass. The largest difference between
  computed and published values was 0.037 points (TYA, accepted range ≈ ±0.09).
- Skipped (`NOT_VERIFIABLE`) when the percentage is not published, when NAV, Price and
  Premium/Discount dates differ, or when NAV or Price is missing.
- A mismatch marks **both** NAV and Price `INCORRECT`, because it cannot be known which one is wrong.

## 6. Portfolio Duration

| Situation | Result |
|---|---|
| Not published (or site shows `N/A`) | `NOT_APPLICABLE` (shown as `-`) |
| Published but unreadable | `MISSING` |
| Readable number (any sign) | `NOT_VERIFIABLE`: the site publishes no date or second source for it |

## 7. Holdings

| # | Rule | Result if it fails |
|---|---|---|
| 1 | Holdings table present | `MISSING` |
| 2 | "As of" date present | `MISSING` (shown as `[as of MISSING]`) |
| 3 | At least one row | `INCORRECT` |
| 4 | Date rules (section 3) | see section 3 |

## 8. Output

- Result line symbol (REQ-001): `✗` if any field is `MISSING` or `INCORRECT`.
- Log: one line per field per ETF, `"<TICKER>: <Field> <STATUS> (<reasons>)"`. `WARNING` for
  `MISSING`/`INCORRECT`, `INFO` otherwise.
- Terminal summary: count of each status per field.

## 9. Future extensions (not implemented)

- Count holdings per ETF in the official "Holdings - All ETFs" Excel file linked on each page
  and compare it with the table row count (would make Holdings independently verifiable).
- External reference sources for NAV, price and duration.

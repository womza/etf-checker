# REQ-001: Per-ETF result line (terminal and log)

| | |
|---|---|
| Status | Implemented (Phase 4); rev. 2 (aligned columns) implemented with Phase 5 |
| Date | 2026-11-02 (rev. 2: 2026-11-02) |
| Related phases | Phase 4 (extraction), Phase 5 (statuses), Phase 6 (reports) |

## 1. Goal

For every ETF checked, print **one summary line** to the terminal (CLI) and write
**the same line** to the run log, so the result of each ETF can be read at a glance.

## 2. Reference format

```
✗ AGGH     NAV: MISSING  |  Price: MISSING  |  Duration:    7.40  |  Holdings: 17 rows [as of 10/30/2026]
```

## 3. Line structure

```
{symbol} {ticker:<8} NAV: {nav:>7}  |  Price: {price:>7}  |  Duration: {duration:>7}  |  Holdings: {holdings}
```

| # | Element | Rule |
|---|---|---|
| 1 | `symbol` | `✓` if the ETF has no errors, `✗` if it has at least one error (see section 5). Followed by one space. |
| 2 | `ticker` | Upper case, left-aligned, padded with spaces to 8 characters, then one space. All lines stay aligned (e.g. `AGGH` + 5 spaces before `NAV:`). |
| 3 | Separator | Exactly `"  \|  "` (two spaces, pipe, two spaces) between fields. |
| 4 | Field order | Always `NAV`, `Price`, `Duration`, `Holdings`. All four fields are always present. |
| 5 | Labels | Literal: `NAV:`, `Price:`, `Duration:`, `Holdings:`, each followed by one space. |
| 6 | Column alignment (rev. 2) | NAV, Price and Duration values are right-aligned in a 7-character column (the width of `MISSING`), so every `\|` lines up across ETFs, including `Duration: -`. Values wider than 7 characters (e.g. `$1000.00`) are shown in full; only that line shifts. Holdings is the last field and is not padded. |

## 4. Field values

| Field | Value found | Value not available |
|---|---|---|
| NAV | `$` followed by the number with 2 decimals, no thousands separator (e.g. `$25.12`) | `MISSING` (includes the site showing `N/A`) |
| Price (Market Price) | Same as NAV (e.g. `$25.10`) | `MISSING` (includes the site showing `N/A`) |
| Duration (Portfolio Duration) | Number with 2 decimals; negative values keep the sign (e.g. `7.40`, `-12.35`) | `-` when not published (non fixed-income ETF). **Not an error.** |
| Holdings | `{N} rows [as of {date as shown on the site}]`; singular `1 row` when N = 1 | `MISSING` when the holdings table is not rendered |

Holdings sub-rules:

- `N` is the total number of rows in the holdings table (individual holdings are not read).
- The `as of` date is shown exactly as published on the page (no reformatting; e.g. `10/30/2026`).
- If the table exists but the date is not found: `{N} rows [as of MISSING]` (counts as an error).
- Values are never invented or rounded beyond the 2-decimal display; the raw value goes to the log detail (section 6).

## 5. Symbol rule (`✓` / `✗`)

`✗` is shown when **any** of the following is true:

- NAV is `MISSING`
- Price is `MISSING`
- Holdings is `MISSING`, or its `as of` date is `MISSING`
- The detail page failed to load or belongs to another ticker
- (Phase 5) any field has status `INCORRECT`

`✓` is shown otherwise. Duration `-` (not applicable) **never** causes `✗`.

Phase 5 `NOT_VERIFIABLE` status: shows `✓` (only errors cause `✗`).

## 6. Log

- The exact same line (identical text, including the symbol) is written to
  `reports/etf_checker_YYYY-MM-DD_HHMMSS.log`, after the standard log prefix:

  ```
  2026-11-02 20:15:03,412 | WARNING  | etf_checker | ✗ AGGH     NAV: MISSING  |  Price: MISSING  |  Duration:    7.40  |  Holdings: 17 rows [as of 10/30/2026]
  ```

- Level: `INFO` for `✓` lines, `WARNING` for `✗` lines (so they can be filtered).
  The `✗` line must **not** be printed twice in the terminal (the console log
  handler must not echo it).
- Technical detail (URL, HTTP status, raw values as read from the page, reason for
  each `MISSING`) is logged as separate lines, **not** added to the summary line.
- The log file stays UTF-8.

## 7. Terminal

- The line replaces the current 3-line block per ETF (`[OK]/[ERROR]`, `URL:`, detail).
- Lines are printed as each ETF is processed (not buffered until the end).
- If the terminal cannot encode `✓`/`✗` (e.g. a non-UTF-8 Windows console), fall back to
  `OK` / `X ` (same width, so columns stay aligned) without crashing. The log always uses `✓`/`✗`.
- The header and the final summary block are unchanged.

## 8. Examples

```
✓ AGGH     NAV:  $21.34  |  Price:  $21.36  |  Duration:    7.40  |  Holdings: 17 rows [as of 10/30/2026]
✓ SPYC     NAV:  $38.02  |  Price:  $38.05  |  Duration:       -  |  Holdings: 9 rows [as of 10/30/2026]
✓ PFIX     NAV:  $45.11  |  Price:  $45.20  |  Duration:  -18.62  |  Holdings: 4 rows [as of 10/30/2026]
✓ SBIL     NAV: $100.09  |  Price: $100.08  |  Duration:       -  |  Holdings: 171 rows [as of 10/30/2026]
✗ AGGH     NAV: MISSING  |  Price: MISSING  |  Duration:    7.40  |  Holdings: 17 rows [as of 10/30/2026]
✗ XYZ      NAV:  $10.00  |  Price:  $10.01  |  Duration:       -  |  Holdings: MISSING
✗ XYZ      NAV: MISSING  |  Price: MISSING  |  Duration:       -  |  Holdings: MISSING
```

(Numeric values are illustrative only, not real data.)

The last example is the line for an ETF whose detail page failed to load; the reason is in the log.

## 9. Acceptance criteria

1. One line per ETF checked, in both terminal and log, with identical text.
2. The reference line from section 2 is reproduced character by character for the
   same input data (unit test with a fixed input).
3. Tickers of different lengths produce aligned `NAV:` columns, and every `|` is at the same
   position on all lines (including `Duration: -`, `MISSING` and `$100.09`).
4. ETF without published duration shows `-` (right-aligned) and can still show `✓`.
5. Negative duration is shown with its sign and does not cause `✗`.
6. `N/A` on the site shows `MISSING` and causes `✗`.
7. `--limit N` prints exactly N lines.
8. No crash on a console without UTF-8 support.

## 10. Impact on existing documentation

The README "Missing data rules" table currently specifies terminal text such as
`NAV: MISSING (site shows N/A)`. With this requirement the parenthetical reason moves
to the log only; the README must be updated when this requirement is implemented.

## 11. Decisions (2026-11-02)

| # | Question | Decision |
|---|---|---|
| Q1 | Should NAV/Price include a `$` sign? | Yes: `$25.12`. `MISSING` has no `$`. |
| Q2 | Holdings date format | Exactly as shown on the site |
| Q3 | Symbol for `NOT_VERIFIABLE` (Phase 5) | `✓` |
| Q4 | When to implement | With Phase 4 (symbol based on MISSING / page errors); Phase 5 adds `INCORRECT` |
| Q5 | Duration published but unreadable | `Duration: MISSING`, counts as an error (`✗`) |
| Q6 | Align the `\|` separators (rev. 2) | Yes: fixed-width, right-aligned NAV / Price / Duration columns |

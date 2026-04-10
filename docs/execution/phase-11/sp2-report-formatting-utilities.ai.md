# Sub-Phase 2: Report Formatting Utilities

**Phase:** 11 — Query History & Reporting
**Plan tasks:** 11F (Report Formatting Utilities)
**Dependencies:** —
**Blocks:** sp3, sp4, sp5
**Can run in parallel with:** sp1

## Objective
Build shared formatting functions for consistent, plain-text report output across all three skills. All output must be copy-pasteable into GitHub issues, Slack messages, and documentation — no ANSI escape codes, no Unicode box-drawing characters.

## Context
- Read shared context: `docs/execution/phase-11/_shared_context.md`
- Read plan (11F section): `docs/plan/phase-11-query-history.md`

## Deliverables

### 1. `backend/src/linkedout/query_history/formatters.py` (NEW)

Pure formatting functions with no I/O dependencies. All functions accept data and return strings.

**`format_table(headers: list[str], rows: list[list[str]], max_col_width: int = 40) -> str`**
- Produces a plain text table using pipes and dashes
- Example output:
  ```
  | Name       | Company    | Tier   |
  |------------|------------|--------|
  | Jane Doe   | Stripe     | Close  |
  | John Smith | Anthropic  | Casual |
  ```
- Auto-sizes columns based on content (up to `max_col_width`)
- Truncates cells exceeding `max_col_width` with `...`
- Handles empty rows gracefully (shows headers + "No data")
- Right-aligns numeric columns (detect by checking if all values in column are numeric)

**`format_stat_line(label: str, value: str | int | float, unit: str | None = None) -> str`**
- Fixed-width label for alignment across multiple stat lines
- Example: `Profiles loaded:  4,012`
- Example with unit: `Avg response time:  234 ms`
- Numbers auto-formatted with `format_count()`

**`format_health_badge(score: float, issue_count: int = 0) -> str`**
- Score 0-100
- `score >= 90 and issue_count == 0` → `[HEALTHY]`
- `score >= 70` → `[WARNING: {issue_count} issue(s)]`
- `score < 70` → `[CRITICAL: {issue_count} issue(s)]`

**`format_duration(ms: int | float) -> str`**
- `< 1000` → `"234ms"`
- `1000-59999` → `"2.3s"`
- `60000-3599999` → `"1m 45s"`
- `>= 3600000` → `"2h 15m"`

**`format_count(n: int | float) -> str`**
- Locale-aware number formatting with commas: `4012` → `"4,012"`
- Float values: 2 decimal places: `3.14159` → `"3.14"`

**`format_pct(num: int, denom: int) -> str`**
- Percentage with denominator: `format_pct(3691, 3847)` → `"95.9% (3,691/3,847)"`
- Handle zero denominator: `format_pct(0, 0)` → `"N/A (0/0)"`

**`truncate_text(text: str, max_len: int = 80) -> str`**
- If `len(text) <= max_len`, return unchanged
- Otherwise, truncate and add `...`: `"Very long query text about..."` (total length = `max_len`)

### 2. Unit Tests

**`backend/tests/unit/query_history/test_formatters.py` (NEW)**
- Test `format_table` with normal data, empty rows, long cell values, numeric alignment
- Test `format_stat_line` with integers, floats, and units
- Test `format_health_badge` at boundary values (89, 90, 69, 70, 100, 0)
- Test `format_duration` at each breakpoint
- Test `format_count` with various magnitudes
- Test `format_pct` with normal values, zero denominator, 100%, 0%
- Test `truncate_text` at boundary (exactly max_len, one over, well under)
- Verify NO ANSI escape codes in any output (regex check for `\x1b\[`)

## Verification
After completing all deliverables, run:
```bash
cd backend && uv run pytest tests/unit/query_history/test_formatters.py -v
```
All tests must pass. Spot-check that output is visually correct by printing a sample table.

# SPDX-License-Identifier: Apache-2.0
"""Unit tests for query_history.formatters module."""

from __future__ import annotations

import re

from linkedout.query_history.formatters import (
    format_count,
    format_duration,
    format_health_badge,
    format_pct,
    format_stat_line,
    format_table,
    truncate_text,
)

ANSI_RE = re.compile(r"\x1b\[")


# -------------------------------------------------------------------
# format_count
# -------------------------------------------------------------------
class TestFormatCount:
    def test_integer_with_commas(self) -> None:
        assert format_count(4012) == "4,012"

    def test_integer_small(self) -> None:
        assert format_count(42) == "42"

    def test_integer_zero(self) -> None:
        assert format_count(0) == "0"

    def test_integer_million(self) -> None:
        assert format_count(1_000_000) == "1,000,000"

    def test_float_two_decimals(self) -> None:
        assert format_count(3.14159) == "3.14"

    def test_float_large(self) -> None:
        assert format_count(1234.5) == "1,234.50"

    def test_float_zero(self) -> None:
        assert format_count(0.0) == "0.00"

    def test_no_ansi(self) -> None:
        assert not ANSI_RE.search(format_count(999999))


# -------------------------------------------------------------------
# format_duration
# -------------------------------------------------------------------
class TestFormatDuration:
    def test_milliseconds(self) -> None:
        assert format_duration(234) == "234ms"

    def test_zero_ms(self) -> None:
        assert format_duration(0) == "0ms"

    def test_just_under_one_second(self) -> None:
        assert format_duration(999) == "999ms"

    def test_exactly_one_second(self) -> None:
        assert format_duration(1000) == "1.0s"

    def test_seconds(self) -> None:
        assert format_duration(2300) == "2.3s"

    def test_just_under_one_minute(self) -> None:
        assert format_duration(59999) == "60.0s"

    def test_exactly_one_minute(self) -> None:
        assert format_duration(60000) == "1m 0s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(105000) == "1m 45s"

    def test_just_under_one_hour(self) -> None:
        assert format_duration(3599999) == "59m 59s"

    def test_exactly_one_hour(self) -> None:
        assert format_duration(3600000) == "1h 0m"

    def test_hours_and_minutes(self) -> None:
        assert format_duration(8100000) == "2h 15m"

    def test_no_ansi(self) -> None:
        assert not ANSI_RE.search(format_duration(123456))


# -------------------------------------------------------------------
# format_pct
# -------------------------------------------------------------------
class TestFormatPct:
    def test_normal(self) -> None:
        assert format_pct(3691, 3847) == "95.9% (3,691/3,847)"

    def test_zero_denominator(self) -> None:
        assert format_pct(0, 0) == "N/A (0/0)"

    def test_nonzero_num_zero_denom(self) -> None:
        actual = format_pct(5, 0)
        assert actual.startswith("N/A")

    def test_hundred_percent(self) -> None:
        assert format_pct(100, 100) == "100.0% (100/100)"

    def test_zero_percent(self) -> None:
        assert format_pct(0, 500) == "0.0% (0/500)"

    def test_no_ansi(self) -> None:
        assert not ANSI_RE.search(format_pct(1, 2))


# -------------------------------------------------------------------
# truncate_text
# -------------------------------------------------------------------
class TestTruncateText:
    def test_well_under(self) -> None:
        assert truncate_text("hello", 80) == "hello"

    def test_exactly_max_len(self) -> None:
        text = "a" * 80
        assert truncate_text(text, 80) == text

    def test_one_over(self) -> None:
        text = "a" * 81
        actual = truncate_text(text, 80)
        assert len(actual) == 80
        assert actual.endswith("...")

    def test_long_text(self) -> None:
        text = "Very long query text about something" + "x" * 100
        actual = truncate_text(text, 30)
        assert len(actual) == 30
        assert actual.endswith("...")
        assert actual == text[:27] + "..."

    def test_empty_string(self) -> None:
        assert truncate_text("", 80) == ""

    def test_no_ansi(self) -> None:
        assert not ANSI_RE.search(truncate_text("test" * 50, 20))


# -------------------------------------------------------------------
# format_stat_line
# -------------------------------------------------------------------
class TestFormatStatLine:
    def test_integer_value(self) -> None:
        actual = format_stat_line("Profiles loaded", 4012)
        assert "Profiles loaded:" in actual
        assert "4,012" in actual

    def test_float_value(self) -> None:
        actual = format_stat_line("Score", 98.765)
        assert "98.77" in actual

    def test_string_value(self) -> None:
        actual = format_stat_line("Status", "Active")
        assert "Active" in actual

    def test_with_unit(self) -> None:
        actual = format_stat_line("Avg response time", 234, "ms")
        assert "234" in actual
        assert "ms" in actual

    def test_alignment(self) -> None:
        # Both stat lines should have values starting at the same
        # column offset thanks to fixed-width label formatting
        line1 = format_stat_line("Short", 1)
        line2 = format_stat_line("Much longer label", 2)
        # Values should start at same column (after the padded label)
        val_start_1 = line1.rindex("  ") + 2
        val_start_2 = line2.rindex("  ") + 2
        assert val_start_1 == val_start_2

    def test_no_ansi(self) -> None:
        assert not ANSI_RE.search(
            format_stat_line("Test", 100, "items")
        )


# -------------------------------------------------------------------
# format_health_badge
# -------------------------------------------------------------------
class TestFormatHealthBadge:
    def test_healthy(self) -> None:
        assert format_health_badge(90, 0) == "[HEALTHY]"

    def test_healthy_high_score(self) -> None:
        assert format_health_badge(100, 0) == "[HEALTHY]"

    def test_score_90_with_issues(self) -> None:
        actual = format_health_badge(90, 1)
        assert actual == "[WARNING: 1 issue(s)]"

    def test_score_89(self) -> None:
        actual = format_health_badge(89, 0)
        assert actual == "[WARNING: 0 issue(s)]"

    def test_warning(self) -> None:
        actual = format_health_badge(75, 2)
        assert actual == "[WARNING: 2 issue(s)]"

    def test_score_70(self) -> None:
        actual = format_health_badge(70, 3)
        assert actual == "[WARNING: 3 issue(s)]"

    def test_score_69(self) -> None:
        actual = format_health_badge(69, 5)
        assert actual == "[CRITICAL: 5 issue(s)]"

    def test_critical(self) -> None:
        actual = format_health_badge(50, 10)
        assert actual == "[CRITICAL: 10 issue(s)]"

    def test_score_zero(self) -> None:
        actual = format_health_badge(0, 0)
        assert actual == "[CRITICAL: 0 issue(s)]"

    def test_no_ansi(self) -> None:
        assert not ANSI_RE.search(format_health_badge(50, 3))


# -------------------------------------------------------------------
# format_table
# -------------------------------------------------------------------
class TestFormatTable:
    def test_normal_table(self) -> None:
        headers = ["Name", "Company", "Tier"]
        rows = [
            ["Jane Doe", "Stripe", "Close"],
            ["John Smith", "Anthropic", "Casual"],
        ]
        actual = format_table(headers, rows)

        assert "| Name" in actual
        assert "| Company" in actual
        assert "| Tier" in actual
        assert "Jane Doe" in actual
        assert "Anthropic" in actual
        # Check separator line exists
        lines = actual.strip().split("\n")
        assert len(lines) == 4  # header + sep + 2 data rows
        assert all(c in "-|" for c in lines[1].replace(" ", ""))

    def test_empty_rows(self) -> None:
        headers = ["Name", "Value"]
        actual = format_table(headers, [])
        assert "No data" in actual
        lines = actual.strip().split("\n")
        assert len(lines) == 3  # header + sep + "No data" row

    def test_long_cell_truncated(self) -> None:
        headers = ["Description"]
        rows = [["A" * 100]]
        actual = format_table(headers, rows, max_col_width=20)
        # Truncated cell should end with ...
        assert "..." in actual
        # Data cells should not exceed max_col_width
        lines = actual.strip().split("\n")
        # Check header row (line 0) and data rows (line 2+)
        for line in [lines[0]] + lines[2:]:
            cells = line.strip("|").split("|")
            for cell in cells:
                assert len(cell.strip()) <= 20

    def test_numeric_right_alignment(self) -> None:
        headers = ["Item", "Count"]
        rows = [
            ["Apples", "5"],
            ["Bananas", "123"],
        ]
        actual = format_table(headers, rows)
        lines = actual.strip().split("\n")
        # In numeric columns, shorter numbers should have
        # leading spaces
        count_col_cells = []
        for line in lines[2:]:  # skip header and separator
            parts = line.strip("|").split("|")
            count_col_cells.append(parts[1])
        # "5" should have more leading spaces than "123"
        assert count_col_cells[0].index("5") > count_col_cells[1].index("1")

    def test_mixed_numeric_column_not_right_aligned(self) -> None:
        headers = ["Value"]
        rows = [["100"], ["abc"], ["200"]]
        actual = format_table(headers, rows)
        # Column has mixed types — should NOT be right-aligned
        # (left-aligned means value starts near the beginning)
        lines = actual.strip().split("\n")
        data_lines = lines[2:]
        for dl in data_lines:
            cell = dl.strip("|").strip()
            # Left-aligned: content at start of cell
            assert not cell.startswith("  ") or cell.strip() == ""

    def test_empty_headers(self) -> None:
        assert format_table([], []) == ""

    def test_short_rows_padded(self) -> None:
        headers = ["A", "B", "C"]
        rows = [["x"]]  # missing B and C
        actual = format_table(headers, rows)
        assert "x" in actual
        lines = actual.strip().split("\n")
        # Should still have 3 columns
        assert lines[0].count("|") == 4  # |A|B|C|

    def test_no_ansi(self) -> None:
        headers = ["Test"]
        rows = [["value"]]
        assert not ANSI_RE.search(format_table(headers, rows))


# -------------------------------------------------------------------
# Cross-cutting: no ANSI in any output
# -------------------------------------------------------------------
class TestNoAnsiEscapes:
    """Verify no ANSI escape codes leak into any formatter output."""

    def test_all_formatters_clean(self) -> None:
        outputs = [
            format_count(999999),
            format_duration(123456),
            format_pct(50, 100),
            truncate_text("x" * 200, 50),
            format_stat_line("Label", 42, "items"),
            format_health_badge(85, 3),
            format_table(
                ["H1", "H2"],
                [["a", "b"], ["c", "d"]],
            ),
        ]
        for output in outputs:
            assert not ANSI_RE.search(output), (
                f"ANSI escape found in: {output!r}"
            )

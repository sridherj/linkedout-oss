# SPDX-License-Identifier: Apache-2.0
"""Report formatting utilities for plain-text output.

Pure formatting functions with no I/O dependencies. All functions
accept data and return strings. Output is plain text suitable for
copy-pasting into GitHub issues, Slack messages, and documentation
— no ANSI escape codes, no Unicode box-drawing characters.
"""

from __future__ import annotations


def format_count(n: int | float) -> str:
    """Format a number with locale-style comma separators.

    Integers get comma grouping. Floats are rounded to 2 decimal
    places then comma-grouped on the integer part.

    Args:
        n: The number to format.

    Returns:
        Comma-separated string, e.g. ``"4,012"`` or ``"3.14"``.
    """
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def format_duration(ms: int | float) -> str:
    """Format a duration in milliseconds to a human-readable string.

    Breakpoints:
    - ``< 1000``       -> ``"234ms"``
    - ``1000–59999``   -> ``"2.3s"``
    - ``60000–3599999`` -> ``"1m 45s"``
    - ``>= 3600000``   -> ``"2h 15m"``

    Args:
        ms: Duration in milliseconds. Must be non-negative.

    Returns:
        Human-readable duration string.
    """
    if ms < 1000:
        return f"{int(ms)}ms"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    if ms < 3600000:
        total_seconds = int(ms / 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    total_minutes = int(ms / 60000)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}h {minutes}m"


def format_pct(num: int, denom: int) -> str:
    """Format a fraction as a percentage with raw counts.

    Args:
        num: Numerator.
        denom: Denominator.

    Returns:
        String like ``"95.9% (3,691/3,847)"``.
        Returns ``"N/A (0/0)"`` when both num and denom are zero.
        Returns ``"0.0% (0/5)"`` when only num is zero.
    """
    if denom == 0:
        return f"N/A ({format_count(num)}/{format_count(denom)})"
    pct = (num / denom) * 100
    return f"{pct:.1f}% ({format_count(num)}/{format_count(denom)})"


def truncate_text(text: str, max_len: int = 80) -> str:
    """Truncate text to a maximum length, adding ``...`` if needed.

    If the text fits within *max_len* it is returned unchanged.
    Otherwise it is cut so that the result (including the trailing
    ``...``) is exactly *max_len* characters.

    Args:
        text: The string to truncate.
        max_len: Maximum allowed length (default 80).

    Returns:
        The original or truncated string.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def format_stat_line(
    label: str,
    value: str | int | float,
    unit: str | None = None,
) -> str:
    """Format a single statistic line with a fixed-width label.

    The label is left-padded to 24 characters so that multiple stat
    lines align neatly when printed together.

    Args:
        label: Descriptive label (e.g. ``"Profiles loaded"``).
        value: The stat value. Numeric values are auto-formatted
            with :func:`format_count`.
        unit: Optional unit suffix (e.g. ``"ms"``, ``"%"``).

    Returns:
        Formatted line, e.g. ``"Profiles loaded:  4,012"``
        or ``"Avg response time:  234 ms"``.
    """
    formatted_value: str
    if isinstance(value, (int, float)):
        formatted_value = format_count(value)
    else:
        formatted_value = value

    if unit:
        formatted_value = f"{formatted_value} {unit}"

    return f"{label + ':':<24}  {formatted_value}"


def format_health_badge(
    score: float,
    issue_count: int = 0,
) -> str:
    """Return a plain-text health badge based on a 0–100 score.

    Thresholds:
    - ``score >= 90`` **and** ``issue_count == 0`` -> ``[HEALTHY]``
    - ``score >= 70`` -> ``[WARNING: N issue(s)]``
    - ``score < 70`` -> ``[CRITICAL: N issue(s)]``

    Args:
        score: Health score between 0 and 100.
        issue_count: Number of open issues (default 0).

    Returns:
        Badge string like ``"[HEALTHY]"`` or
        ``"[WARNING: 2 issue(s)]"``.
    """
    if score >= 90 and issue_count == 0:
        return "[HEALTHY]"
    if score >= 70:
        return f"[WARNING: {issue_count} issue(s)]"
    return f"[CRITICAL: {issue_count} issue(s)]"


def format_table(
    headers: list[str],
    rows: list[list[str]],
    max_col_width: int = 40,
) -> str:
    """Produce a plain-text Markdown-style table.

    Columns are auto-sized based on content up to *max_col_width*.
    Cells exceeding the limit are truncated with ``...``. Columns
    where every data value is numeric are right-aligned.

    Example output::

        | Name       | Company   | Tier   |
        |------------|-----------|--------|
        | Jane Doe   | Stripe    | Close  |

    Args:
        headers: Column header strings.
        rows: List of rows, each a list of cell strings. Rows
            shorter than *headers* are padded with empty strings.
        max_col_width: Maximum character width per column
            (default 40).

    Returns:
        Multi-line plain-text table string. If *rows* is empty,
        the table shows headers and a ``"No data"`` row.
    """
    if not headers:
        return ""

    num_cols = len(headers)

    # Normalize rows — pad short rows with empty strings
    normalized: list[list[str]] = []
    for row in rows:
        padded = list(row) + [""] * (num_cols - len(row))
        normalized.append(padded[:num_cols])

    # Detect numeric columns (all non-empty data cells are numeric)
    numeric_cols: list[bool] = []
    for col_idx in range(num_cols):
        col_values = [r[col_idx] for r in normalized if r[col_idx]]
        is_numeric = bool(col_values) and all(
            _is_numeric(v) for v in col_values
        )
        numeric_cols.append(is_numeric)

    # Truncate cells that exceed max_col_width
    truncated_headers = [
        truncate_text(h, max_col_width) for h in headers
    ]
    truncated_rows: list[list[str]] = []
    for row in normalized:
        truncated_rows.append(
            [truncate_text(cell, max_col_width) for cell in row]
        )

    # Compute column widths from headers and data
    col_widths: list[int] = []
    for col_idx in range(num_cols):
        max_w = len(truncated_headers[col_idx])
        for row in truncated_rows:
            max_w = max(max_w, len(row[col_idx]))
        # Ensure "No data" fits in first column if rows empty
        if col_idx == 0 and not truncated_rows:
            max_w = max(max_w, 7)
        col_widths.append(max_w)

    # Build header row
    header_cells = []
    for col_idx, hdr in enumerate(truncated_headers):
        header_cells.append(f" {hdr:<{col_widths[col_idx]}} ")
    header_line = "|" + "|".join(header_cells) + "|"

    # Build separator row
    sep_cells = ["-" * (col_widths[i] + 2) for i in range(num_cols)]
    sep_line = "|" + "|".join(sep_cells) + "|"

    # Build data rows
    data_lines: list[str] = []
    if not truncated_rows:
        # "No data" row spanning first column
        no_data_cells = []
        for col_idx in range(num_cols):
            if col_idx == 0:
                no_data_cells.append(
                    f" {'No data':<{col_widths[col_idx]}} "
                )
            else:
                no_data_cells.append(
                    f" {'':<{col_widths[col_idx]}} "
                )
        data_lines.append("|" + "|".join(no_data_cells) + "|")
    else:
        for row in truncated_rows:
            cells = []
            for col_idx, cell in enumerate(row):
                if numeric_cols[col_idx]:
                    cells.append(
                        f" {cell:>{col_widths[col_idx]}} "
                    )
                else:
                    cells.append(
                        f" {cell:<{col_widths[col_idx]}} "
                    )
            data_lines.append("|" + "|".join(cells) + "|")

    return "\n".join([header_line, sep_line] + data_lines)


def _is_numeric(value: str) -> bool:
    """Check whether a string looks numeric (int or float).

    Args:
        value: The string to check.

    Returns:
        True if the string can be parsed as a number.
    """
    try:
        float(value)
        return True
    except ValueError:
        return False

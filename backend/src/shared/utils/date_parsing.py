# SPDX-License-Identifier: Apache-2.0
"""Date parsing utilities for LinkedIn/Apify data."""
import calendar
from datetime import date
from typing import Optional


# Month abbreviation lookup (case-insensitive)
_MONTH_MAP = {name.lower(): num for num, name in enumerate(calendar.month_abbr) if name}
_MONTH_FULL_MAP = {name.lower(): num for num, name in enumerate(calendar.month_name) if name}


def parse_month_name(month_text: str) -> Optional[int]:
    """Parse a month name/abbreviation to its number (1-12).

    Handles: 'Feb' -> 2, 'August' -> 8, 'feb' -> 2
    Returns None for invalid/empty input.
    """
    if not month_text or not month_text.strip():
        return None

    key = month_text.strip().lower()

    # Try abbreviation first (Jan, Feb, ...)
    if key in _MONTH_MAP:
        return _MONTH_MAP[key]

    # Try full name (January, February, ...)
    if key in _MONTH_FULL_MAP:
        return _MONTH_FULL_MAP[key]

    # Try matching first 3 chars as abbreviation
    if len(key) > 3 and key[:3] in _MONTH_MAP:
        return _MONTH_MAP[key[:3]]

    return None


def parse_apify_date(date_obj: dict) -> Optional[date]:
    """Parse an Apify-style date dict to a Python date.

    Expected format: {'year': 2024, 'text': 'Feb'} or {'year': 2024, 'month': 2}
    endDate with text='Present' returns None.

    Returns date(year, month, 1) or None if unparseable.
    """
    if not date_obj or not isinstance(date_obj, dict):
        return None

    year = date_obj.get('year')
    if not year or not isinstance(year, int):
        return None

    # Check for 'Present'
    text = date_obj.get('text', '')
    if isinstance(text, str) and text.strip().lower() == 'present':
        return None

    # Try explicit month field first
    month = date_obj.get('month')
    if isinstance(month, int) and 1 <= month <= 12:
        return date(year, month, 1)

    # Try parsing month from text
    if text:
        month = parse_month_name(str(text))
        if month:
            return date(year, month, 1)

    return None


def parse_linkedin_csv_date(date_str: str) -> Optional[date]:
    """Parse a LinkedIn CSV date string to a Python date.

    Handles: '22 Feb 2026', '7 Feb 2026', '07 Feb 2026'
    Returns None for empty/invalid input.
    """
    if not date_str or not date_str.strip():
        return None

    parts = date_str.strip().split()
    if len(parts) != 3:
        return None

    try:
        day = int(parts[0])
    except (ValueError, TypeError):
        return None

    month = parse_month_name(parts[1])
    if not month:
        return None

    try:
        year = int(parts[2])
    except (ValueError, TypeError):
        return None

    try:
        return date(year, month, day)
    except ValueError:
        return None

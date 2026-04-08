# SPDX-License-Identifier: Apache-2.0
"""Tests for date parsing utilities."""
from datetime import date

from shared.utils.date_parsing import parse_month_name, parse_apify_date, parse_linkedin_csv_date


class TestParseMonthName:
    def test_abbreviation(self):
        assert parse_month_name('Feb') == 2
        assert parse_month_name('Aug') == 8
        assert parse_month_name('Dec') == 12

    def test_full_name(self):
        assert parse_month_name('January') == 1
        assert parse_month_name('February') == 2

    def test_case_insensitive(self):
        assert parse_month_name('feb') == 2
        assert parse_month_name('MARCH') == 3

    def test_none_returns_none(self):
        assert parse_month_name('') is None
        assert parse_month_name('   ') is None

    def test_invalid_returns_none(self):
        assert parse_month_name('Xyz') is None
        assert parse_month_name('13') is None


class TestParseApifyDate:
    def test_with_text_month(self):
        assert parse_apify_date({'year': 2024, 'text': 'Feb'}) == date(2024, 2, 1)

    def test_with_explicit_month(self):
        assert parse_apify_date({'year': 2024, 'month': 8}) == date(2024, 8, 1)

    def test_present_returns_none(self):
        assert parse_apify_date({'year': 2024, 'text': 'Present'}) is None
        assert parse_apify_date({'year': 2024, 'text': 'present'}) is None

    def test_missing_year_returns_none(self):
        assert parse_apify_date({'text': 'Feb'}) is None

    def test_none_returns_none(self):
        assert parse_apify_date(None) is None

    def test_empty_dict_returns_none(self):
        assert parse_apify_date({}) is None

    def test_non_dict_returns_none(self):
        assert parse_apify_date('2024-02') is None


class TestParseLinkedinCsvDate:
    def test_standard_format(self):
        assert parse_linkedin_csv_date('22 Feb 2026') == date(2026, 2, 22)

    def test_single_digit_day(self):
        assert parse_linkedin_csv_date('7 Feb 2026') == date(2026, 2, 7)

    def test_zero_padded_day(self):
        assert parse_linkedin_csv_date('07 Feb 2026') == date(2026, 2, 7)

    def test_empty_returns_none(self):
        assert parse_linkedin_csv_date('') is None
        assert parse_linkedin_csv_date('   ') is None

    def test_invalid_format_returns_none(self):
        assert parse_linkedin_csv_date('2026-02-22') is None
        assert parse_linkedin_csv_date('Feb 2026') is None

    def test_invalid_month_returns_none(self):
        assert parse_linkedin_csv_date('22 Xyz 2026') is None

    def test_invalid_day_returns_none(self):
        assert parse_linkedin_csv_date('32 Feb 2026') is None

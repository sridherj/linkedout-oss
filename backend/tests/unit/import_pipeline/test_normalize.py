# SPDX-License-Identifier: Apache-2.0
"""Unit tests for email and phone normalization."""
import pytest

from linkedout.import_pipeline.normalize import normalize_email, normalize_phone


class TestNormalizeEmail:
    def test_lowercase_and_strip(self):
        assert normalize_email('  Alice@Example.COM  ') == 'alice@example.com'

    def test_already_clean(self):
        assert normalize_email('user@test.com') == 'user@test.com'

    def test_empty_string(self):
        assert normalize_email('') == ''

    def test_none_returns_empty(self):
        assert normalize_email(None) == ''

    def test_missing_at_sign(self):
        assert normalize_email('not-an-email') == ''

    def test_missing_dot_after_at(self):
        assert normalize_email('user@localhost') == ''

    def test_whitespace_only(self):
        assert normalize_email('   ') == ''


class TestNormalizePhone:
    def test_indian_with_country_code(self):
        assert normalize_phone('+91 98765 43210') == '+919876543210'

    def test_indian_without_country_code(self):
        assert normalize_phone('9876543210', default_country='IN') == '+919876543210'

    def test_us_format(self):
        assert normalize_phone('+1 (650) 253-0000', default_country='US') == '+16502530000'

    def test_us_bare_digits(self):
        assert normalize_phone('6502530000', default_country='US') == '+16502530000'

    def test_unparseable_returns_none(self):
        assert normalize_phone('abc') is None

    def test_empty_returns_none(self):
        assert normalize_phone('') is None

    def test_none_returns_none(self):
        assert normalize_phone(None) is None

    def test_whitespace_only_returns_none(self):
        assert normalize_phone('   ') is None

    def test_too_short_returns_none(self):
        assert normalize_phone('123') is None

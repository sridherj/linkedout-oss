# SPDX-License-Identifier: Apache-2.0
"""Tests for LinkedIn URL normalization utility."""
import pytest

from shared.utils.linkedin_url import normalize_linkedin_url


class TestNormalizeLinkedinUrl:
    def test_standard_url(self):
        assert normalize_linkedin_url('https://www.linkedin.com/in/johndoe') == 'https://www.linkedin.com/in/johndoe'

    def test_strips_query_params(self):
        assert normalize_linkedin_url(
            'https://www.linkedin.com/in/JohnDoe/?originalSubdomain=uk'
        ) == 'https://www.linkedin.com/in/johndoe'

    def test_strips_country_prefix(self):
        assert normalize_linkedin_url(
            'https://uk.linkedin.com/in/JohnDoe/'
        ) == 'https://www.linkedin.com/in/johndoe'

    def test_strips_fr_country_prefix(self):
        assert normalize_linkedin_url(
            'https://fr.linkedin.com/in/JaneDoe'
        ) == 'https://www.linkedin.com/in/janedoe'

    def test_strips_trailing_slash(self):
        assert normalize_linkedin_url(
            'https://www.linkedin.com/in/johndoe/'
        ) == 'https://www.linkedin.com/in/johndoe'

    def test_forces_lowercase(self):
        assert normalize_linkedin_url(
            'https://www.linkedin.com/in/JohnDoe'
        ) == 'https://www.linkedin.com/in/johndoe'

    def test_empty_string_returns_none(self):
        assert normalize_linkedin_url('') is None

    def test_none_like_whitespace_returns_none(self):
        assert normalize_linkedin_url('   ') is None

    def test_invalid_url_returns_none(self):
        assert normalize_linkedin_url('https://example.com/profile') is None

    def test_url_encoded_characters_decoded(self):
        """Percent-encoded chars are decoded so DB-stored and Apify-returned URLs match."""
        result = normalize_linkedin_url(
            'https://www.linkedin.com/in/%f0%9f%a7%bf-test'
        )
        assert result == 'https://www.linkedin.com/in/\U0001f9ff-test'

    def test_no_scheme(self):
        assert normalize_linkedin_url(
            'www.linkedin.com/in/johndoe'
        ) == 'https://www.linkedin.com/in/johndoe'

    def test_multiple_query_params(self):
        assert normalize_linkedin_url(
            'https://www.linkedin.com/in/JohnDoe?utm_source=google&ref=abc'
        ) == 'https://www.linkedin.com/in/johndoe'

    def test_missing_in_segment_returns_none(self):
        assert normalize_linkedin_url('https://www.linkedin.com/company/acme') is None

    def test_hyphenated_slug(self):
        assert normalize_linkedin_url(
            'https://www.linkedin.com/in/john-doe-123abc/'
        ) == 'https://www.linkedin.com/in/john-doe-123abc'

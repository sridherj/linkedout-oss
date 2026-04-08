# SPDX-License-Identifier: Apache-2.0
"""Tests for company matching and deduplication utilities."""
from shared.utils.company_matcher import (
    normalize_company_name,
    normalize_company_linkedin_url,
    CompanyMatcher,
)


class TestNormalizeCompanyName:
    def test_basic(self):
        assert normalize_company_name('Acme Inc.') == 'acme inc'

    def test_strips_special_chars(self):
        assert normalize_company_name('O\'Reilly & Associates') == 'oreilly associates'

    def test_collapses_whitespace(self):
        assert normalize_company_name('  Foo   Bar  ') == 'foo bar'

    def test_empty_returns_empty(self):
        assert normalize_company_name('') == ''
        assert normalize_company_name(None) == ''

    def test_preserves_numbers(self):
        assert normalize_company_name('3M Company') == '3m company'

    def test_unicode_stripped(self):
        assert normalize_company_name('Café Co.') == 'caf co'


class TestNormalizeCompanyLinkedinUrl:
    def test_standard_url(self):
        assert normalize_company_linkedin_url(
            'https://www.linkedin.com/company/microsoft/'
        ) == 'https://www.linkedin.com/company/microsoft'

    def test_numeric_id(self):
        assert normalize_company_linkedin_url(
            'https://www.linkedin.com/company/1035/'
        ) == 'https://www.linkedin.com/company/1035'

    def test_strips_query_params(self):
        assert normalize_company_linkedin_url(
            'https://www.linkedin.com/company/microsoft?trk=foo'
        ) == 'https://www.linkedin.com/company/microsoft'

    def test_forces_lowercase(self):
        assert normalize_company_linkedin_url(
            'https://www.linkedin.com/company/Microsoft'
        ) == 'https://www.linkedin.com/company/microsoft'

    def test_search_url_returns_none(self):
        assert normalize_company_linkedin_url(
            'https://www.linkedin.com/search/results/all/?keywords=acme'
        ) is None

    def test_profile_url_returns_none(self):
        assert normalize_company_linkedin_url(
            'https://www.linkedin.com/in/johndoe'
        ) is None

    def test_empty_returns_none(self):
        assert normalize_company_linkedin_url('') is None
        assert normalize_company_linkedin_url(None) is None

    def test_non_string_returns_none(self):
        assert normalize_company_linkedin_url(123) is None

    def test_url_with_hash(self):
        assert normalize_company_linkedin_url(
            'https://www.linkedin.com/company/microsoft#about'
        ) == 'https://www.linkedin.com/company/microsoft'


class TestCompanyMatcher:
    def test_create_new_company(self):
        matcher = CompanyMatcher()
        result = matcher.match_or_create('Acme Inc')
        assert result == 'Acme Inc'
        assert len(matcher) == 1

    def test_match_by_name(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Acme Inc.')
        result = matcher.match_or_create('acme inc')
        assert result == 'Acme Inc.'
        assert len(matcher) == 1

    def test_match_by_url(self):
        matcher = CompanyMatcher()
        matcher.match_or_create(
            'Acme Inc',
            linkedin_url='https://www.linkedin.com/company/acme/'
        )
        result = matcher.match_or_create(
            'ACME Corporation',
            linkedin_url='https://www.linkedin.com/company/acme'
        )
        assert result == 'Acme Inc'
        assert len(matcher) == 1

    def test_url_match_trumps_different_name(self):
        matcher = CompanyMatcher()
        matcher.match_or_create(
            'Microsoft',
            linkedin_url='https://www.linkedin.com/company/microsoft'
        )
        result = matcher.match_or_create(
            'Microsoft Corporation',
            linkedin_url='https://www.linkedin.com/company/microsoft'
        )
        assert result == 'Microsoft'
        assert len(matcher) == 1

    def test_merges_url_on_name_match(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Acme Inc')
        matcher.match_or_create(
            'acme inc',
            linkedin_url='https://www.linkedin.com/company/acme'
        )
        company = matcher.get_company('Acme Inc')
        assert company['linkedin_url'] == 'https://www.linkedin.com/company/acme'
        assert len(matcher) == 1

    def test_merges_universal_name(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Acme Inc', universal_name=None)
        matcher.match_or_create('acme inc', universal_name='acme-inc')
        company = matcher.get_company('Acme Inc')
        assert company['universal_name'] == 'acme-inc'

    def test_empty_name_returns_none(self):
        matcher = CompanyMatcher()
        assert matcher.match_or_create('') is None
        assert matcher.match_or_create(None) is None
        assert matcher.match_or_create('   ') is None
        assert len(matcher) == 0

    def test_get_all_companies(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('A Corp')
        matcher.match_or_create('B Corp')
        companies = matcher.get_all_companies()
        assert len(companies) == 2
        names = {c['canonical_name'] for c in companies}
        assert names == {'A Corp', 'B Corp'}

    def test_get_company_not_found(self):
        matcher = CompanyMatcher()
        assert matcher.get_company('NonExistent') is None

    def test_distinct_companies_not_merged(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Apple Inc')
        matcher.match_or_create('Google LLC')
        assert len(matcher) == 2

    # --- Subsidiary resolution tests ---

    def test_subsidiary_resolves_to_parent(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Google')
        result = matcher.match_or_create('Google Cloud - Minnesota')
        assert result == 'Google'
        assert len(matcher) == 1

    def test_subsidiary_aws_to_amazon(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Amazon')
        result = matcher.match_or_create('Amazon Web Services')
        assert result == 'Amazon'
        assert len(matcher) == 1

    def test_subsidiary_google_deepmind(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Google')
        result = matcher.match_or_create('Google DeepMind')
        assert result == 'Google'
        assert len(matcher) == 1

    def test_subsidiary_facebook_to_meta(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('Meta')
        result = matcher.match_or_create('Facebook')
        assert result == 'Meta'
        assert len(matcher) == 1

    def test_subsidiary_netapp_variants(self):
        matcher = CompanyMatcher()
        matcher.match_or_create('NetApp')
        assert matcher.match_or_create('NetApp India') == 'NetApp'
        assert matcher.match_or_create('NetApp Inc') == 'NetApp'
        assert len(matcher) == 1

    def test_subsidiary_regional_suffix_stripped(self):
        """Regional suffix regex: 'Accenture India' → 'Accenture'."""
        matcher = CompanyMatcher()
        matcher.match_or_create('Accenture')
        result = matcher.match_or_create('Accenture India')
        assert result == 'Accenture'
        assert len(matcher) == 1

    def test_subsidiary_caches_variant_name(self):
        """After resolving, the variant name should be cached for direct future lookups."""
        matcher = CompanyMatcher()
        matcher.match_or_create('Google')
        matcher.match_or_create('Google Cloud')
        # Second lookup of same variant should be instant (name cache hit, not subsidiary resolution)
        result = matcher.match_or_create('Google Cloud')
        assert result == 'Google'
        assert len(matcher) == 1

    def test_subsidiary_no_parent_in_matcher_creates_new(self):
        """If the parent isn't in the matcher yet, subsidiary creates a new entry."""
        matcher = CompanyMatcher()
        result = matcher.match_or_create('Google India')
        # Parent 'Google' not registered — so it creates 'Google India' as new
        assert result == 'Google India'
        assert len(matcher) == 1

    def test_subsidiary_different_linkedin_urls_still_merge(self):
        """Subsidiaries with different LinkedIn URLs merge to parent."""
        matcher = CompanyMatcher()
        matcher.match_or_create('Google', linkedin_url='https://www.linkedin.com/company/google')
        result = matcher.match_or_create(
            'Google Cloud - Minnesota',
            linkedin_url='https://www.linkedin.com/company/1441'
        )
        assert result == 'Google'
        assert len(matcher) == 1

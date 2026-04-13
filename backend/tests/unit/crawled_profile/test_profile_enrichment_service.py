# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ProfileEnrichmentService constructor — matcher injection."""
from unittest.mock import MagicMock, patch

from linkedout.crawled_profile.services.profile_enrichment_service import ProfileEnrichmentService
from shared.utils.company_matcher import CompanyMatcher


class TestCompanyMatcherInjection:
    """Verify optional company_matcher skips or triggers _preload_companies()."""

    @patch.object(ProfileEnrichmentService, '_preload_companies')
    def test_init_with_provided_matcher_skips_preload(self, mock_preload):
        matcher = CompanyMatcher()
        by_canonical = {'Acme': MagicMock()}

        svc = ProfileEnrichmentService(
            MagicMock(), company_matcher=matcher, company_by_canonical=by_canonical,
        )

        mock_preload.assert_not_called()
        assert svc._company_matcher is matcher
        assert svc._company_by_canonical is by_canonical

    @patch.object(ProfileEnrichmentService, '_preload_companies')
    def test_init_without_matcher_preloads(self, mock_preload):
        svc = ProfileEnrichmentService(MagicMock())

        mock_preload.assert_called_once()
        assert isinstance(svc._company_matcher, CompanyMatcher)
        assert svc._company_by_canonical == {}

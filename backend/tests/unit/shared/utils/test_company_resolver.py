# SPDX-License-Identifier: Apache-2.0
"""Unit tests for resolve_company utility."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from shared.utils.company_resolver import resolve_company


class TestResolveCompany:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = MagicMock()
        self.matcher = MagicMock()
        self.cache: dict = {}

    def test_none_company_name_returns_none(self):
        """None company_name returns None immediately."""
        result = resolve_company(self.session, self.matcher, self.cache, None)
        assert result is None
        self.matcher.match_or_create.assert_not_called()

    def test_match_existing_company_returns_id(self):
        """Existing company in cache: returns its ID without creating."""
        existing = MagicMock()
        existing.id = 'co_existing_123'
        self.cache['acme'] = existing
        self.matcher.match_or_create.return_value = 'acme'

        result = resolve_company(
            self.session, self.matcher, self.cache,
            'Acme Corp',
        )

        assert result == 'co_existing_123'
        self.session.add.assert_not_called()

    def test_create_new_company(self):
        """New company: creates entity, flushes, updates cache."""
        self.matcher.match_or_create.return_value = 'newco'

        result = resolve_company(
            self.session, self.matcher, self.cache,
            'NewCo Inc',
            linkedin_url='https://linkedin.com/company/newco',
            universal_name='newco',
        )

        # Should have added and flushed
        self.session.add.assert_called_once()
        self.session.flush.assert_called_once()
        # Cache should be updated
        assert 'newco' in self.cache

    def test_cache_hit_on_second_call(self):
        """Second call for same company uses cache, no duplicate creation."""
        self.matcher.match_or_create.return_value = 'acme'

        # First call: creates
        resolve_company(self.session, self.matcher, self.cache, 'Acme Corp')
        assert self.session.add.call_count == 1

        # Second call: cache hit
        result = resolve_company(self.session, self.matcher, self.cache, 'Acme Corp')
        assert self.session.add.call_count == 1  # no new add

    def test_matcher_returns_none(self):
        """If matcher returns None canonical, return None."""
        self.matcher.match_or_create.return_value = None

        result = resolve_company(self.session, self.matcher, self.cache, 'Weird Co')
        assert result is None

    def test_integrity_error_falls_back_to_select(self):
        """Concurrent insert race: SAVEPOINT rollback + SELECT fallback."""
        self.matcher.match_or_create.return_value = 'GreenDot Digital'

        # Simulate flush raising IntegrityError (concurrent request committed first)
        self.session.flush.side_effect = IntegrityError(
            statement='INSERT INTO company ...', params={}, orig=Exception('duplicate key'),
        )

        # Mock the SELECT fallback
        existing = MagicMock()
        existing.id = 'co_existing_green'
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = existing
        self.session.execute.return_value = mock_result

        result = resolve_company(
            self.session, self.matcher, self.cache,
            'GreenDot Digital',
            linkedin_url='https://linkedin.com/company/greendot-digital',
        )

        assert result == 'co_existing_green'
        assert self.cache['GreenDot Digital'] is existing

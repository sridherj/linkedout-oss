# SPDX-License-Identifier: Apache-2.0
"""Tests for base controller utilities.

These tests verify the shared controller utility functions work correctly.
"""

import pytest
from unittest.mock import Mock, MagicMock
from typing import Generator

from fastapi import Request

from common.controllers.base_controller_utils import build_pagination_links, create_service_dependency
from common.schemas.base_response_schema import PaginationLinks
from shared.infra.db.db_session_manager import DbSessionType


# =============================================================================
# TESTS FOR build_pagination_links
# =============================================================================


class TestBuildPaginationLinks:
    """Tests for the build_pagination_links utility function."""

    @pytest.fixture
    def mock_request(self) -> Mock:
        """Create a mock FastAPI Request object."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.scheme = 'https'
        request.url.netloc = 'api.example.com'
        return request

    def test_builds_basic_pagination_links(self, mock_request: Mock):
        """Verify basic pagination links are built correctly."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=100,
            limit=20,
            offset=0,
            params={},
        )

        assert isinstance(links, PaginationLinks)
        assert links.self == 'https://api.example.com/tenants/tenant_1/bus/bu_1/lots?limit=20&offset=0'
        assert links.first == 'https://api.example.com/tenants/tenant_1/bus/bu_1/lots?limit=20&offset=0'
        assert links.last == 'https://api.example.com/tenants/tenant_1/bus/bu_1/lots?limit=20&offset=80'
        assert links.prev is None  # First page, no previous
        assert links.next == 'https://api.example.com/tenants/tenant_1/bus/bu_1/lots?limit=20&offset=20'

    def test_builds_links_with_offset(self, mock_request: Mock):
        """Verify pagination links with offset include prev link."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='bins',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=100,
            limit=20,
            offset=40,
            params={},
        )

        assert links.self == 'https://api.example.com/tenants/tenant_1/bus/bu_1/bins?limit=20&offset=40'
        assert links.prev == 'https://api.example.com/tenants/tenant_1/bus/bu_1/bins?limit=20&offset=20'
        assert links.next == 'https://api.example.com/tenants/tenant_1/bus/bu_1/bins?limit=20&offset=60'

    def test_builds_links_for_last_page(self, mock_request: Mock):
        """Verify last page has no next link."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=100,
            limit=20,
            offset=80,
            params={},
        )

        assert links.next is None  # Last page, no next
        assert links.prev == 'https://api.example.com/tenants/tenant_1/bus/bu_1/lots?limit=20&offset=60'

    def test_builds_links_with_filter_params(self, mock_request: Mock):
        """Verify filter parameters are included in links."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=50,
            limit=20,
            offset=0,
            params={'status': 'active', 'commodity_id': 'cm_123'},
        )

        assert 'status=active' in links.self
        assert 'commodity_id=cm_123' in links.self
        assert 'status=active' in links.first
        assert 'commodity_id=cm_123' in links.first

    def test_builds_links_with_list_params(self, mock_request: Mock):
        """Verify list parameters are expanded correctly."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=50,
            limit=20,
            offset=0,
            params={'statuses': ['active', 'pending']},
        )

        assert 'statuses=active' in links.self
        assert 'statuses=pending' in links.self

    def test_excludes_none_params(self, mock_request: Mock):
        """Verify None parameters are excluded from links."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=50,
            limit=20,
            offset=0,
            params={'status': 'active', 'commodity_id': None},
        )

        assert 'status=active' in links.self
        assert 'commodity_id' not in links.self

    def test_excludes_limit_offset_from_params(self, mock_request: Mock):
        """Verify limit and offset in params are not duplicated."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=50,
            limit=20,
            offset=0,
            params={'limit': 999, 'offset': 999, 'status': 'active'},
        )

        # Should use the explicit limit/offset args, not params
        assert 'limit=20' in links.self
        assert 'offset=0' in links.self
        assert 'limit=999' not in links.self
        assert 'offset=999' not in links.self

    def test_handles_single_page(self, mock_request: Mock):
        """Verify single page has no last link when page_count <= 1."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=10,
            limit=20,
            offset=0,
            params={},
        )

        assert links.last is None
        assert links.prev is None
        assert links.next is None

    def test_handles_zero_total(self, mock_request: Mock):
        """Verify zero total is handled correctly."""
        links = build_pagination_links(
            request=mock_request,
            entity_path='lots',
            tenant_id='tenant_1',
            bu_id='bu_1',
            total=0,
            limit=20,
            offset=0,
            params={},
        )

        assert links.last is None
        assert links.prev is None
        assert links.next is None

    def test_works_with_different_entity_paths(self, mock_request: Mock):
        """Verify different entity paths work correctly."""
        for entity_path in ['lots', 'bins', 'demands', 'commodities']:
            links = build_pagination_links(
                request=mock_request,
                entity_path=entity_path,
                tenant_id='tenant_1',
                bu_id='bu_1',
                total=100,
                limit=20,
                offset=0,
                params={},
            )

            assert f'/bus/bu_1/{entity_path}?' in links.self


# =============================================================================
# TESTS FOR create_service_dependency
# =============================================================================


class TestCreateServiceDependency:
    """Tests for the create_service_dependency factory function."""

    def test_creates_service_with_read_session(self, monkeypatch):
        """Verify service is created with read session."""
        mock_session = Mock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = Mock(return_value=mock_session)
        mock_context_manager.__exit__ = Mock(return_value=False)

        mock_db_session_manager = Mock()
        mock_db_session_manager.get_session = Mock(return_value=mock_context_manager)

        # Patch the db_session_manager in the module
        monkeypatch.setattr(
            'common.controllers.base_controller_utils.db_session_manager',
            mock_db_session_manager,
        )

        # Create a mock service class
        mock_service_class = Mock()
        mock_service_instance = Mock()
        mock_service_class.return_value = mock_service_instance

        # Use the factory
        gen = create_service_dependency(mock_service_class, DbSessionType.READ)
        service = next(gen)

        assert service == mock_service_instance
        mock_db_session_manager.get_session.assert_called_once_with(DbSessionType.READ, app_user_id=None)
        mock_service_class.assert_called_once_with(mock_session)

    def test_creates_service_with_write_session(self, monkeypatch):
        """Verify service is created with write session."""
        mock_session = Mock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = Mock(return_value=mock_session)
        mock_context_manager.__exit__ = Mock(return_value=False)

        mock_db_session_manager = Mock()
        mock_db_session_manager.get_session = Mock(return_value=mock_context_manager)

        monkeypatch.setattr(
            'common.controllers.base_controller_utils.db_session_manager',
            mock_db_session_manager,
        )

        mock_service_class = Mock()
        mock_service_instance = Mock()
        mock_service_class.return_value = mock_service_instance

        gen = create_service_dependency(mock_service_class, DbSessionType.WRITE)
        service = next(gen)

        assert service == mock_service_instance
        mock_db_session_manager.get_session.assert_called_once_with(DbSessionType.WRITE, app_user_id=None)

    def test_defaults_to_read_session(self, monkeypatch):
        """Verify default session type is READ."""
        mock_session = Mock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = Mock(return_value=mock_session)
        mock_context_manager.__exit__ = Mock(return_value=False)

        mock_db_session_manager = Mock()
        mock_db_session_manager.get_session = Mock(return_value=mock_context_manager)

        monkeypatch.setattr(
            'common.controllers.base_controller_utils.db_session_manager',
            mock_db_session_manager,
        )

        mock_service_class = Mock()

        gen = create_service_dependency(mock_service_class)
        next(gen)

        mock_db_session_manager.get_session.assert_called_once_with(DbSessionType.READ, app_user_id=None)

    def test_is_generator(self, monkeypatch):
        """Verify the function returns a generator."""
        mock_session = Mock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = Mock(return_value=mock_session)
        mock_context_manager.__exit__ = Mock(return_value=False)

        mock_db_session_manager = Mock()
        mock_db_session_manager.get_session = Mock(return_value=mock_context_manager)

        monkeypatch.setattr(
            'common.controllers.base_controller_utils.db_session_manager',
            mock_db_session_manager,
        )

        mock_service_class = Mock()

        result = create_service_dependency(mock_service_class)

        assert isinstance(result, Generator)

# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for CrawledProfileService.

Verifies that CrawledProfileService is correctly wired.
CrawledProfile is a shared entity (no tenant/BU), following the Company pattern.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.crawled_profile.repositories.crawled_profile_repository import CrawledProfileRepository
from linkedout.crawled_profile.services.crawled_profile_service import CrawledProfileService
from linkedout.crawled_profile.schemas.crawled_profile_schema import CrawledProfileSchema
from linkedout.crawled_profile.schemas.crawled_profile_api_schema import (
    ListCrawledProfilesRequestSchema,
    CreateCrawledProfileRequestSchema,
    UpdateCrawledProfileRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(CrawledProfileRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = CrawledProfileService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = CrawledProfileEntity(
        linkedin_url='https://linkedin.com/in/johndoe',
        full_name='John Doe',
        data_source='apify',
        has_enriched_data=False,
    )
    entity.id = 'cp_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestCrawledProfileServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = CrawledProfileService(mock_session)
        assert svc is not None

    def test_has_repository(self, service):
        assert service._repository is not None

    def test_has_crud_methods(self):
        svc = CrawledProfileService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_crawled_profiles', None))
        assert callable(getattr(svc, 'create_crawled_profile', None))
        assert callable(getattr(svc, 'create_crawled_profiles', None))
        assert callable(getattr(svc, 'update_crawled_profile', None))
        assert callable(getattr(svc, 'get_crawled_profile_by_id', None))
        assert callable(getattr(svc, 'delete_crawled_profile_by_id', None))


class TestCrawledProfileServiceListProfiles:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListCrawledProfilesRequestSchema()
        profiles, total = service.list_crawled_profiles(req)

        assert total == 1
        assert len(profiles) == 1
        assert isinstance(profiles[0], CrawledProfileSchema)
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_handles_empty(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListCrawledProfilesRequestSchema()
        profiles, total = service.list_crawled_profiles(req)

        assert total == 0
        assert profiles == []


class TestCrawledProfileServiceCreateProfile:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateCrawledProfileRequestSchema(
            linkedin_url='https://linkedin.com/in/johndoe',
            data_source='apify',
        )
        result = service.create_crawled_profile(req)

        assert isinstance(result, CrawledProfileSchema)
        assert result.linkedin_url == 'https://linkedin.com/in/johndoe'
        mock_repository.create.assert_called_once()


class TestCrawledProfileServiceUpdateProfile:
    def test_updates_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateCrawledProfileRequestSchema(
            crawled_profile_id='cp_test123',
            seniority_level='Senior',
        )
        result = service.update_crawled_profile(req)

        assert isinstance(result, CrawledProfileSchema)
        mock_repository.get_by_id.assert_called_once_with('cp_test123')

    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateCrawledProfileRequestSchema(
            crawled_profile_id='cp_nonexistent',
            seniority_level='Senior',
        )
        with pytest.raises(ValueError, match='CrawledProfile not found'):
            service.update_crawled_profile(req)

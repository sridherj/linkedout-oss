# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ExperienceService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.experience.repositories.experience_repository import ExperienceRepository
from linkedout.experience.services.experience_service import ExperienceService
from linkedout.experience.schemas.experience_schema import ExperienceSchema
from linkedout.experience.schemas.experience_api_schema import (
    ListExperiencesRequestSchema,
    CreateExperienceRequestSchema,
    UpdateExperienceRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(ExperienceRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = ExperienceService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = ExperienceEntity(
        crawled_profile_id='cp_test123',
        position='Software Engineer',
        company_name='Acme Corp',
    )
    entity.id = 'exp_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestExperienceServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = ExperienceService(mock_session)
        assert svc is not None

    def test_has_repository(self, service):
        assert service._repository is not None

    def test_has_crud_methods(self):
        svc = ExperienceService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_experiences', None))
        assert callable(getattr(svc, 'create_experience', None))
        assert callable(getattr(svc, 'create_experiences', None))
        assert callable(getattr(svc, 'update_experience', None))
        assert callable(getattr(svc, 'get_experience_by_id', None))
        assert callable(getattr(svc, 'delete_experience_by_id', None))


class TestExperienceServiceListExperiences:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListExperiencesRequestSchema()
        experiences, total = service.list_experiences(req)

        assert total == 1
        assert len(experiences) == 1
        assert isinstance(experiences[0], ExperienceSchema)
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_handles_empty(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListExperiencesRequestSchema()
        experiences, total = service.list_experiences(req)

        assert total == 0
        assert experiences == []


class TestExperienceServiceCreateExperience:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateExperienceRequestSchema(
            crawled_profile_id='cp_test123',
            position='Software Engineer',
        )
        result = service.create_experience(req)

        assert isinstance(result, ExperienceSchema)
        assert result.position == 'Software Engineer'
        mock_repository.create.assert_called_once()


class TestExperienceServiceUpdateExperience:
    def test_updates_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateExperienceRequestSchema(
            experience_id='exp_test123',
            position='Senior Engineer',
        )
        result = service.update_experience(req)

        assert isinstance(result, ExperienceSchema)
        mock_repository.get_by_id.assert_called_once_with('exp_test123')

    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateExperienceRequestSchema(
            experience_id='exp_nonexistent',
            position='Senior Engineer',
        )
        with pytest.raises(ValueError, match='Experience not found'):
            service.update_experience(req)

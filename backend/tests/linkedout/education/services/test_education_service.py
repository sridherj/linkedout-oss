# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for EducationService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.education.entities.education_entity import EducationEntity
from linkedout.education.repositories.education_repository import EducationRepository
from linkedout.education.services.education_service import EducationService
from linkedout.education.schemas.education_schema import EducationSchema
from linkedout.education.schemas.education_api_schema import (
    ListEducationsRequestSchema,
    CreateEducationRequestSchema,
    UpdateEducationRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(EducationRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = EducationService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = EducationEntity(
        crawled_profile_id='cp_test123',
        school_name='MIT',
        degree='BS',
    )
    entity.id = 'edu_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestEducationServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = EducationService(mock_session)
        assert svc is not None

    def test_has_repository(self, service):
        assert service._repository is not None

    def test_has_crud_methods(self):
        svc = EducationService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_educations', None))
        assert callable(getattr(svc, 'create_education', None))
        assert callable(getattr(svc, 'create_educations', None))
        assert callable(getattr(svc, 'update_education', None))
        assert callable(getattr(svc, 'get_education_by_id', None))
        assert callable(getattr(svc, 'delete_education_by_id', None))


class TestEducationServiceListEducations:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListEducationsRequestSchema()
        educations, total = service.list_educations(req)

        assert total == 1
        assert len(educations) == 1
        assert isinstance(educations[0], EducationSchema)
        mock_repository.list_with_filters.assert_called_once()
        mock_repository.count_with_filters.assert_called_once()

    def test_handles_empty(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListEducationsRequestSchema()
        educations, total = service.list_educations(req)

        assert total == 0
        assert educations == []


class TestEducationServiceCreateEducation:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateEducationRequestSchema(
            crawled_profile_id='cp_test123',
            school_name='MIT',
        )
        result = service.create_education(req)

        assert isinstance(result, EducationSchema)
        assert result.school_name == 'MIT'
        mock_repository.create.assert_called_once()


class TestEducationServiceUpdateEducation:
    def test_updates_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateEducationRequestSchema(
            education_id='edu_test123',
            degree='MS',
        )
        result = service.update_education(req)

        assert isinstance(result, EducationSchema)
        mock_repository.get_by_id.assert_called_once_with('edu_test123')

    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateEducationRequestSchema(
            education_id='edu_nonexistent',
            degree='MS',
        )
        with pytest.raises(ValueError, match='Education not found'):
            service.update_education(req)

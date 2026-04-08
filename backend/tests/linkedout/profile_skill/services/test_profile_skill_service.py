# SPDX-License-Identifier: Apache-2.0
"""Wiring tests for ProfileSkillService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from linkedout.profile_skill.entities.profile_skill_entity import ProfileSkillEntity
from linkedout.profile_skill.repositories.profile_skill_repository import ProfileSkillRepository
from linkedout.profile_skill.services.profile_skill_service import ProfileSkillService
from linkedout.profile_skill.schemas.profile_skill_schema import ProfileSkillSchema
from linkedout.profile_skill.schemas.profile_skill_api_schema import (
    ListProfileSkillsRequestSchema,
    CreateProfileSkillRequestSchema,
    UpdateProfileSkillRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(ProfileSkillRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = ProfileSkillService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = ProfileSkillEntity(
        crawled_profile_id='cp_test123',
        skill_name='Python',
        endorsement_count=5,
    )
    entity.id = 'psk_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestProfileSkillServiceWiring:
    def test_can_instantiate(self, mock_session):
        svc = ProfileSkillService(mock_session)
        assert svc is not None

    def test_has_repository(self, service):
        assert service._repository is not None

    def test_has_crud_methods(self):
        svc = ProfileSkillService(create_autospec(Session, instance=True))
        assert callable(getattr(svc, 'list_profile_skills', None))
        assert callable(getattr(svc, 'create_profile_skill', None))
        assert callable(getattr(svc, 'create_profile_skills', None))
        assert callable(getattr(svc, 'update_profile_skill', None))
        assert callable(getattr(svc, 'get_profile_skill_by_id', None))
        assert callable(getattr(svc, 'delete_profile_skill_by_id', None))


class TestProfileSkillServiceList:
    def test_calls_repository(self, service, mock_repository, mock_entity):
        mock_repository.list_with_filters.return_value = [mock_entity]
        mock_repository.count_with_filters.return_value = 1

        req = ListProfileSkillsRequestSchema()
        items, total = service.list_profile_skills(req)

        assert total == 1
        assert len(items) == 1
        assert isinstance(items[0], ProfileSkillSchema)

    def test_handles_empty(self, service, mock_repository):
        mock_repository.list_with_filters.return_value = []
        mock_repository.count_with_filters.return_value = 0

        req = ListProfileSkillsRequestSchema()
        items, total = service.list_profile_skills(req)

        assert total == 0
        assert items == []


class TestProfileSkillServiceCreate:
    def test_creates_entity(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity

        req = CreateProfileSkillRequestSchema(
            crawled_profile_id='cp_test123',
            skill_name='Python',
        )
        result = service.create_profile_skill(req)

        assert isinstance(result, ProfileSkillSchema)
        assert result.skill_name == 'Python'
        mock_repository.create.assert_called_once()


class TestProfileSkillServiceUpdate:
    def test_updates_provided_fields(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        mock_repository.update.return_value = mock_entity

        req = UpdateProfileSkillRequestSchema(
            profile_skill_id='psk_test123',
            endorsement_count=10,
        )
        result = service.update_profile_skill(req)

        assert isinstance(result, ProfileSkillSchema)
        mock_repository.get_by_id.assert_called_once_with('psk_test123')

    def test_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None

        req = UpdateProfileSkillRequestSchema(
            profile_skill_id='psk_nonexistent',
            endorsement_count=10,
        )
        with pytest.raises(ValueError, match='ProfileSkill not found'):
            service.update_profile_skill(req)

# SPDX-License-Identifier: Apache-2.0
"""Wiring and integration tests for AgentRunRepository."""
import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session

from common.repositories.base_repository import BaseRepository, FilterSpec
from common.entities.agent_run_entity import AgentRunEntity
from common.repositories.agent_run_repository import AgentRunRepository
from tests.seed_db import SeedDb, TableName


class TestAgentRunRepositoryWiring:
    def test_inherits_from_base_repository(self):
        assert issubclass(AgentRunRepository, BaseRepository)

    def test_entity_class_configured(self):
        assert AgentRunRepository._entity_class == AgentRunEntity

    def test_default_sort_field_configured(self):
        assert AgentRunRepository._default_sort_field == 'created_at'

    def test_entity_name_configured(self):
        assert AgentRunRepository._entity_name == 'agent_run'

    def test_filter_specs_defined(self):
        repo = AgentRunRepository(Mock(spec=Session))
        specs = repo._get_filter_specs()
        assert isinstance(specs, list)
        assert all(isinstance(s, FilterSpec) for s in specs)
        spec_names = {s.field_name for s in specs}
        assert {'agent_type', 'status'}.issubset(spec_names)

    def test_filter_specs_have_correct_types(self):
        repo = AgentRunRepository(Mock(spec=Session))
        specs_by_name = {s.field_name: s for s in repo._get_filter_specs()}
        assert specs_by_name['agent_type'].filter_type == 'eq'
        assert specs_by_name['status'].filter_type == 'eq'


INTEGRATION_SEED_CONFIG = SeedDb.SeedConfig(
    tables_to_populate=[TableName.TENANT, TableName.BU],
    tenant_count=1, bu_count_per_tenant=1,
)


@pytest.mark.seed_config(INTEGRATION_SEED_CONFIG)
class TestAgentRunRepositoryIntegration:
    @pytest.fixture(scope='class')
    def class_db_resources(self, class_scoped_isolated_db_session):
        return class_scoped_isolated_db_session

    @pytest.fixture(scope='class')
    def db_session(self, class_db_resources):
        session, _ = class_db_resources
        return session

    @pytest.fixture(scope='class')
    def seeded_data(self, class_db_resources):
        _, data = class_db_resources
        return data

    @pytest.fixture
    def repository(self, db_session):
        return AgentRunRepository(db_session)

    def test_create_generates_id_with_prefix(self, repository, db_session, seeded_data):
        tenant = seeded_data[TableName.TENANT][0]
        bu = seeded_data[TableName.BU][0]
        entity = AgentRunEntity(
            tenant_id=tenant.id, bu_id=bu.id,
            agent_type='task_triage', status='PENDING',
            input_params={'task_id': 'task-test-001'},
        )
        created = repository.create(entity)
        db_session.commit()
        assert created.id is not None
        assert created.id.startswith('arn_')

    def test_list_with_agent_type_filter(self, repository, db_session, seeded_data):
        tenant = seeded_data[TableName.TENANT][0]
        bu = seeded_data[TableName.BU][0]
        results = repository.list_with_filters(
            tenant_id=tenant.id, bu_id=bu.id, agent_type='task_triage',
        )
        assert len(results) >= 1

    def test_list_with_status_filter(self, repository, db_session, seeded_data):
        tenant = seeded_data[TableName.TENANT][0]
        bu = seeded_data[TableName.BU][0]
        results = repository.list_with_filters(
            tenant_id=tenant.id, bu_id=bu.id, status='PENDING',
        )
        assert len(results) >= 1

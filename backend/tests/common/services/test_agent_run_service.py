# SPDX-License-Identifier: Apache-2.0
"""Service tests for AgentRun."""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, create_autospec
from sqlalchemy.orm import Session

from common.entities.agent_run_entity import AgentRunEntity
from common.repositories.agent_run_repository import AgentRunRepository
from common.services.agent_run_service import AgentRunService
from common.schemas.agent_run_schema import (
    AgentRunSchema,
    AgentRunStatus,
    CreateAgentRunRequestSchema,
    UpdateAgentRunRequestSchema,
    ListAgentRunsRequestSchema,
    GetAgentRunByIdRequestSchema,
    DeleteAgentRunByIdRequestSchema,
)


@pytest.fixture
def mock_session():
    return create_autospec(Session, instance=True, spec_set=True)


@pytest.fixture
def mock_repository():
    return create_autospec(AgentRunRepository, instance=True, spec_set=True)


@pytest.fixture
def service(mock_session, mock_repository):
    svc = AgentRunService(mock_session)
    svc._repository = mock_repository
    return svc


@pytest.fixture
def mock_entity():
    entity = AgentRunEntity(
        tenant_id='tenant_1', bu_id='bu_1',
        agent_type='task_triage', status='PENDING',
        input_params={'task_id': 'task-001'},
    )
    entity.id = 'arn_test123'
    entity.created_at = datetime.now(timezone.utc)
    entity.updated_at = datetime.now(timezone.utc)
    return entity


class TestAgentRunServiceWiring:
    def test_repository_class(self):
        assert AgentRunService._repository_class == AgentRunRepository

    def test_schema_class(self):
        assert AgentRunService._schema_class == AgentRunSchema

    def test_entity_class(self):
        assert AgentRunService._entity_class == AgentRunEntity

    def test_entity_id_field(self):
        assert AgentRunService._entity_id_field == 'agent_run_id'


class TestAgentRunServiceFilterExtraction:
    def test_extracts_all_filters(self, service):
        req = ListAgentRunsRequestSchema(
            tenant_id='t', bu_id='b',
            agent_type='task_triage', status=AgentRunStatus.PENDING,
        )
        kwargs = service._extract_filter_kwargs(req)
        assert kwargs['agent_type'] == 'task_triage'
        assert kwargs['status'] == AgentRunStatus.PENDING

    def test_handles_none(self, service):
        req = ListAgentRunsRequestSchema(tenant_id='t', bu_id='b')
        kwargs = service._extract_filter_kwargs(req)
        assert kwargs['agent_type'] is None
        assert kwargs['status'] is None


class TestAgentRunServiceEntityCreation:
    def test_creates_entity(self, service):
        req = CreateAgentRunRequestSchema(
            tenant_id='t', bu_id='b',
            agent_type='task_triage', status=AgentRunStatus.PENDING,
            input_params={'task_id': 'task-001'},
        )
        entity = service._create_entity_from_request(req)
        assert entity.agent_type == 'task_triage'
        assert entity.status == AgentRunStatus.PENDING
        assert entity.input_params == {'task_id': 'task-001'}


class TestAgentRunServiceEntityUpdate:
    def test_updates_provided_fields(self, service, mock_entity):
        req = UpdateAgentRunRequestSchema(
            tenant_id='t', bu_id='b', agent_run_id='arn_test123',
            status=AgentRunStatus.COMPLETED, error_message='done',
        )
        service._update_entity_from_request(mock_entity, req)
        assert mock_entity.status == AgentRunStatus.COMPLETED
        assert mock_entity.error_message == 'done'

    def test_none_does_not_change(self, service, mock_entity):
        original_status = mock_entity.status
        original_agent_type = mock_entity.agent_type
        req = UpdateAgentRunRequestSchema(
            tenant_id='t', bu_id='b', agent_run_id='arn_test123',
        )
        service._update_entity_from_request(mock_entity, req)
        assert mock_entity.status == original_status
        assert mock_entity.agent_type == original_agent_type

    def test_updates_llm_fields(self, service, mock_entity):
        req = UpdateAgentRunRequestSchema(
            tenant_id='t', bu_id='b', agent_run_id='arn_test123',
            llm_cost_usd=0.05, llm_latency_ms=1200,
            llm_metadata={'model': 'claude-sonnet-4-6'},
        )
        service._update_entity_from_request(mock_entity, req)
        assert mock_entity.llm_cost_usd == 0.05
        assert mock_entity.llm_latency_ms == 1200
        assert mock_entity.llm_metadata == {'model': 'claude-sonnet-4-6'}


class TestAgentRunServiceCRUD:
    def test_create_returns_schema(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity
        req = CreateAgentRunRequestSchema(
            tenant_id='tenant_1', bu_id='bu_1',
            agent_type='task_triage', status=AgentRunStatus.PENDING,
        )
        result = service.create_entity(req)
        assert isinstance(result, AgentRunSchema)
        mock_repository.create.assert_called_once()

    def test_get_by_id_returns_schema(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        req = GetAgentRunByIdRequestSchema(
            tenant_id='tenant_1', bu_id='bu_1', agent_run_id='arn_test123',
        )
        result = service.get_entity_by_id(req)
        assert isinstance(result, AgentRunSchema)
        assert result.id == 'arn_test123'

    def test_get_by_id_not_found(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None
        req = GetAgentRunByIdRequestSchema(
            tenant_id='t', bu_id='b', agent_run_id='nonexistent',
        )
        result = service.get_entity_by_id(req)
        assert result is None

    def test_delete_not_found_raises(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None
        req = DeleteAgentRunByIdRequestSchema(
            tenant_id='t', bu_id='b', agent_run_id='nonexistent',
        )
        with pytest.raises(ValueError, match='not found'):
            service.delete_entity_by_id(req)


class TestAgentRunServiceCreateAgentRun:
    def test_create_agent_run_returns_schema(self, service, mock_repository, mock_entity):
        mock_repository.create.return_value = mock_entity
        result = service.create_agent_run(
            tenant_id='tenant_1', bu_id='bu_1',
            agent_type='task_triage',
            input_params={'task_id': 'task-001'},
        )
        assert isinstance(result, AgentRunSchema)
        mock_repository.create.assert_called_once()


class TestAgentRunServiceUpdateStatus:
    def test_update_status_pending_to_running(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        now = datetime.now(timezone.utc)
        result = service.update_status(
            tenant_id='tenant_1', bu_id='bu_1',
            agent_run_id='arn_test123',
            status=AgentRunStatus.RUNNING,
            started_at=now,
        )
        assert mock_entity.status == AgentRunStatus.RUNNING
        assert mock_entity.started_at == now

    def test_update_status_with_error(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        result = service.update_status(
            tenant_id='tenant_1', bu_id='bu_1',
            agent_run_id='arn_test123',
            status=AgentRunStatus.FAILED,
            error_message='LLM timeout',
        )
        assert mock_entity.status == AgentRunStatus.FAILED
        assert mock_entity.error_message == 'LLM timeout'

    def test_update_status_with_llm_metrics(self, service, mock_repository, mock_entity):
        mock_repository.get_by_id.return_value = mock_entity
        result = service.update_status(
            tenant_id='tenant_1', bu_id='bu_1',
            agent_run_id='arn_test123',
            status=AgentRunStatus.COMPLETED,
            llm_metrics={
                'llm_cost_usd': 0.05,
                'llm_latency_ms': 1200,
                'llm_input': {'prompt': 'test'},
                'llm_output': {'result': 'done'},
                'llm_metadata': {'model': 'claude-sonnet-4-6'},
            },
        )
        assert mock_entity.status == AgentRunStatus.COMPLETED
        assert mock_entity.llm_cost_usd == 0.05
        assert mock_entity.llm_latency_ms == 1200

    def test_update_status_not_found(self, service, mock_repository):
        mock_repository.get_by_id.return_value = None
        result = service.update_status(
            tenant_id='t', bu_id='b',
            agent_run_id='nonexistent',
            status=AgentRunStatus.RUNNING,
        )
        assert result is None

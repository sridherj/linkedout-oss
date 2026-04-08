# SPDX-License-Identifier: Apache-2.0
"""Service layer for AgentRun business logic."""
from datetime import datetime
from typing import Any, Optional

from common.entities.agent_run_entity import AgentRunEntity
from common.repositories.agent_run_repository import AgentRunRepository
from common.schemas.agent_run_schema import (
    AgentRunSchema,
    AgentRunStatus,
    CreateAgentRunRequestSchema,
)
from common.services.base_service import BaseService
from shared.utilities.logger import get_logger

logger = get_logger(__name__)


class AgentRunService(
    BaseService[AgentRunEntity, AgentRunSchema, AgentRunRepository]
):
    """
    Service layer for AgentRun business logic.

    Inherits common CRUD operations from BaseService.
    Adds agent-run-specific convenience methods.
    """

    _repository_class = AgentRunRepository
    _schema_class = AgentRunSchema
    _entity_class = AgentRunEntity
    _entity_name = 'agent_run'
    _entity_id_field = 'agent_run_id'

    def _extract_filter_kwargs(self, list_request: Any) -> dict:
        """Extract filter keyword arguments from list request."""
        return {
            'agent_type': list_request.agent_type,
            'status': list_request.status,
        }

    def _create_entity_from_request(self, create_request: Any) -> AgentRunEntity:
        """Create an AgentRunEntity from create request."""
        json_safe = create_request.model_dump(mode='json')
        return AgentRunEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            agent_type=create_request.agent_type,
            status=create_request.status,
            input_params=json_safe.get('input_params'),
        )

    def _update_entity_from_request(
        self, entity: AgentRunEntity, update_request: Any
    ) -> None:
        """Update an AgentRunEntity from update request."""
        for field in (
            'status', 'error_message', 'started_at', 'completed_at',
            'output', 'llm_input', 'llm_output', 'llm_cost_usd',
            'llm_latency_ms', 'llm_metadata',
        ):
            value = getattr(update_request, field, None)
            if value is not None:
                setattr(entity, field, value)

    def create_agent_run(
        self,
        tenant_id: str,
        bu_id: str,
        agent_type: str,
        input_params: Optional[dict] = None,
    ) -> AgentRunSchema:
        """
        Create a new agent run record with PENDING status.

        Args:
            tenant_id: Tenant ID.
            bu_id: Business unit ID.
            agent_type: Type of agent.
            input_params: Input parameters for the agent.

        Returns:
            Created AgentRunSchema.
        """
        request = CreateAgentRunRequestSchema(
            tenant_id=tenant_id,
            bu_id=bu_id,
            agent_type=agent_type,
            status=AgentRunStatus.PENDING,
            input_params=input_params,
        )
        return self.create_entity(request)

    def update_status(
        self,
        tenant_id: str,
        bu_id: str,
        agent_run_id: str,
        status: AgentRunStatus,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        output: Optional[dict] = None,
        llm_metrics: Optional[dict] = None,
    ) -> Optional[AgentRunSchema]:
        """
        Update the status of an agent run.

        Args:
            tenant_id: Tenant ID.
            bu_id: Business unit ID.
            agent_run_id: The agent run record's ID.
            status: New status.
            error_message: Error message if failed.
            started_at: When execution started.
            completed_at: When execution finished.
            output: Agent output data.
            llm_metrics: LLM metrics dict from agent.get_llm_metrics().

        Returns:
            Updated AgentRunSchema, or None if not found.
        """
        entity = self._repository.get_by_id(
            tenant_id=tenant_id,
            bu_id=bu_id,
            entity_id=agent_run_id,
        )
        if not entity:
            logger.warning(f'Agent run not found: {agent_run_id}')
            return None

        entity.status = status
        if error_message is not None:
            entity.error_message = error_message
        if started_at is not None:
            entity.started_at = started_at
        if completed_at is not None:
            entity.completed_at = completed_at
        if output is not None:
            entity.output = output
        if llm_metrics:
            entity.llm_input = llm_metrics.get('llm_input')
            entity.llm_output = llm_metrics.get('llm_output')
            entity.llm_cost_usd = llm_metrics.get('llm_cost_usd')
            entity.llm_latency_ms = llm_metrics.get('llm_latency_ms')
            entity.llm_metadata = llm_metrics.get('llm_metadata')

        self._session.flush()
        self._session.refresh(entity)
        return self._schema_class.model_validate(entity)

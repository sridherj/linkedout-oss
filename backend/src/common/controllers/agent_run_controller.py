# SPDX-License-Identifier: Apache-2.0
"""Controller for AgentRun endpoints using CRUDRouterFactory."""
from typing import Annotated

from fastapi import BackgroundTasks, Body, Depends, Request

from common.controllers.crud_router_factory import CRUDRouterConfig, create_crud_router
from common.schemas.agent_run_schema import (
    AgentRunStatus,
    CreateAgentRunRequestSchema,
    CreateAgentRunResponseSchema,
    CreateAgentRunsRequestSchema,
    CreateAgentRunsResponseSchema,
    DeleteAgentRunByIdRequestSchema,
    GetAgentRunByIdRequestSchema,
    GetAgentRunByIdResponseSchema,
    InvokeAgentRequestSchema,
    InvokeAgentResponseSchema,
    ListAgentRunsRequestSchema,
    ListAgentRunsResponseSchema,
    UpdateAgentRunRequestSchema,
    UpdateAgentRunResponseSchema,
)
from common.services.agent_run_service import AgentRunService
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

_config = CRUDRouterConfig(
    prefix='/tenants/{tenant_id}/bus/{bu_id}/agent-runs',
    tags=['agent-runs'],
    service_class=AgentRunService,
    entity_name='agent_run',
    entity_name_plural='agent_runs',
    list_request_schema=ListAgentRunsRequestSchema,
    list_response_schema=ListAgentRunsResponseSchema,
    create_request_schema=CreateAgentRunRequestSchema,
    create_response_schema=CreateAgentRunResponseSchema,
    create_bulk_request_schema=CreateAgentRunsRequestSchema,
    create_bulk_response_schema=CreateAgentRunsResponseSchema,
    update_request_schema=UpdateAgentRunRequestSchema,
    update_response_schema=UpdateAgentRunResponseSchema,
    get_by_id_request_schema=GetAgentRunByIdRequestSchema,
    get_by_id_response_schema=GetAgentRunByIdResponseSchema,
    delete_by_id_request_schema=DeleteAgentRunByIdRequestSchema,
    meta_fields=['agent_type', 'status', 'sort_by', 'sort_order'],
)

_result = create_crud_router(_config)
agent_run_router = _result.router
_get_agent_run_service = _result.get_service
_get_write_agent_run_service = _result.get_write_service


# ── Custom invoke endpoint ───────────────────────────────────────────


def _run_agent_background(**kwargs) -> None:
    """Wrap execute_agent so background-task exceptions don't propagate."""
    from common.services.agent_executor_service import execute_agent

    try:
        execute_agent(**kwargs)
    except Exception:
        pass  # already handled inside execute_agent (status -> FAILED)


@agent_run_router.post(
    '/invoke',
    status_code=202,
    response_model=InvokeAgentResponseSchema,
    summary='Invoke an agent asynchronously',
)
def invoke_agent(
    request: Request,
    tenant_id: str,
    bu_id: str,
    invoke_request: Annotated[InvokeAgentRequestSchema, Body()],
    background_tasks: BackgroundTasks,
) -> InvokeAgentResponseSchema:
    """
    Invoke an agent asynchronously.

    Creates an AgentRun record synchronously (PENDING), then schedules
    execution in the background. Returns 202 Accepted with the
    ``agent_run_id`` so the caller can poll for status.
    """
    db_manager = request.app.state.db_manager
    with db_manager.get_session(DbSessionType.WRITE) as session:
        write_service = AgentRunService(session)
        agent_run_schema = write_service.create_agent_run(
            tenant_id=tenant_id,
            bu_id=bu_id,
            agent_type=invoke_request.agent_type,
            input_params=invoke_request.input_params,
        )

    background_tasks.add_task(
        _run_agent_background,
        tenant_id=tenant_id,
        bu_id=bu_id,
        agent_type=invoke_request.agent_type,
        input_params=invoke_request.input_params,
        agent_run_id=agent_run_schema.id,
    )

    return InvokeAgentResponseSchema(
        agent_run_id=agent_run_schema.id,
        status=AgentRunStatus.PENDING,
        message='Agent run created and scheduled for execution.',
    )

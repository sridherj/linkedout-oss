# SPDX-License-Identifier: Apache-2.0
"""Schemas for AgentRun entity and API endpoints."""
from datetime import datetime
from enum import StrEnum
from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from common.schemas.base_enums_schemas import SortOrder
from common.schemas.base_request_schema import BaseRequestSchema, PaginateRequestSchema
from common.schemas.base_response_schema import BaseResponseSchema, PaginateResponseSchema


# ── Enums ────────────────────────────────────────────────────────────


class AgentRunStatus(StrEnum):
    """Status of an agent run."""

    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class AgentRunSortByFields(StrEnum):
    """Fields available for sorting agent runs."""

    CREATED_AT = 'created_at'
    STARTED_AT = 'started_at'
    STATUS = 'status'
    AGENT_TYPE = 'agent_type'


# ── Core schema ──────────────────────────────────────────────────────


class AgentRunSchema(BaseModel):
    """Full schema for AgentRun entity with database fields."""

    id: Annotated[str, Field(description='Primary key agent run ID')]
    tenant_id: Annotated[str, Field(description='Tenant ID')]
    bu_id: Annotated[str, Field(description='Business Unit ID')]
    agent_type: Annotated[str, Field(description='Type of agent')]
    status: Annotated[str, Field(description='Current status of the run')]
    started_at: Annotated[Optional[datetime], Field(description='When execution started', default=None)]
    completed_at: Annotated[Optional[datetime], Field(description='When execution finished', default=None)]
    error_message: Annotated[Optional[str], Field(description='Error message if failed', default=None)]
    input_params: Annotated[Optional[dict], Field(description='Input parameters', default=None)]
    output: Annotated[Optional[dict], Field(description='Agent output', default=None)]
    llm_input: Annotated[Optional[dict], Field(description='LLM input', default=None)]
    llm_output: Annotated[Optional[dict], Field(description='LLM output', default=None)]
    llm_cost_usd: Annotated[Optional[float], Field(description='LLM cost', default=None)]
    llm_latency_ms: Annotated[Optional[int], Field(description='LLM latency', default=None)]
    llm_metadata: Annotated[Optional[dict], Field(description='LLM metadata', default=None)]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── API request schemas ──────────────────────────────────────────────


class ListAgentRunsRequestSchema(PaginateRequestSchema):
    """Request schema for listing agent runs with filters and pagination."""

    tenant_id: Annotated[
        Optional[str], Field(None, description='Tenant ID')
    ] = None
    bu_id: Annotated[
        Optional[str], Field(None, description='Business unit ID')
    ] = None
    sort_by: Annotated[
        AgentRunSortByFields,
        Field(default=AgentRunSortByFields.CREATED_AT),
    ] = AgentRunSortByFields.CREATED_AT
    sort_order: Annotated[
        SortOrder, Field(default=SortOrder.DESC)
    ] = SortOrder.DESC
    agent_type: Annotated[
        Optional[str], Field(None, description='Filter by agent type')
    ] = None
    status: Annotated[
        Optional[AgentRunStatus], Field(None, description='Filter by status')
    ] = None


class CreateAgentRunRequestSchema(BaseRequestSchema):
    """Internal request schema for creating an agent run record."""

    tenant_id: Annotated[
        Optional[str], Field(None, description='Tenant ID')
    ] = None
    bu_id: Annotated[
        Optional[str], Field(None, description='Business unit ID')
    ] = None
    agent_type: Annotated[str, Field(description='Type of agent')]
    status: Annotated[
        AgentRunStatus, Field(default=AgentRunStatus.PENDING)
    ] = AgentRunStatus.PENDING
    input_params: Annotated[
        Optional[dict], Field(None, description='Input parameters')
    ] = None


class UpdateAgentRunRequestSchema(BaseRequestSchema):
    """Internal request schema for updating an agent run."""

    tenant_id: Annotated[
        Optional[str], Field(None, description='Tenant ID')
    ] = None
    bu_id: Annotated[
        Optional[str], Field(None, description='Business unit ID')
    ] = None
    agent_run_id: Annotated[
        Optional[str], Field(None, description='Agent run ID')
    ] = None
    status: Annotated[
        Optional[AgentRunStatus], Field(None, description='New status')
    ] = None
    error_message: Annotated[
        Optional[str], Field(None, description='Error message if failed')
    ] = None
    started_at: Annotated[
        Optional[datetime], Field(None, description='When execution started')
    ] = None
    completed_at: Annotated[
        Optional[datetime], Field(None, description='When execution finished')
    ] = None
    output: Annotated[
        Optional[dict], Field(None, description='Agent output')
    ] = None
    llm_input: Annotated[
        Optional[dict], Field(None, description='LLM input')
    ] = None
    llm_output: Annotated[
        Optional[dict], Field(None, description='LLM output')
    ] = None
    llm_cost_usd: Annotated[
        Optional[float], Field(None, description='LLM cost')
    ] = None
    llm_latency_ms: Annotated[
        Optional[int], Field(None, description='LLM latency')
    ] = None
    llm_metadata: Annotated[
        Optional[dict], Field(None, description='LLM metadata')
    ] = None


class GetAgentRunByIdRequestSchema(BaseRequestSchema):
    """Request schema for getting an agent run by ID."""

    tenant_id: Annotated[
        Optional[str], Field(None, description='Tenant ID')
    ] = None
    bu_id: Annotated[
        Optional[str], Field(None, description='Business unit ID')
    ] = None
    agent_run_id: Annotated[
        Optional[str], Field(None, description='Agent run ID')
    ] = None


class InvokeAgentRequestSchema(BaseModel):
    """Request schema for invoking an agent asynchronously."""

    agent_type: Annotated[str, Field(description='Type of agent to invoke')]
    input_params: Annotated[
        Optional[dict],
        Field(None, description='Agent-specific parameters'),
    ] = None


class InvokeAgentResponseSchema(BaseModel):
    """Response schema for agent invocation (202 Accepted)."""

    agent_run_id: Annotated[str, Field(
        description='The agent run ID. Poll GET /agent-runs/{agent_run_id} for status.',
    )]
    status: Annotated[AgentRunStatus, Field(description='Initial status (PENDING)')]
    message: Annotated[
        Optional[str],
        Field(None, description='Optional message'),
    ] = None


# ── API response schemas ─────────────────────────────────────────────


class ListAgentRunsResponseSchema(PaginateResponseSchema):
    """Response schema for listing agent runs."""

    agent_runs: Annotated[
        List[AgentRunSchema],
        Field(default_factory=list, description='List of agent runs'),
    ]
    meta: Annotated[
        Optional[dict], Field(None, description='Request metadata')
    ] = None


class DeleteAgentRunByIdRequestSchema(BaseRequestSchema):
    """Request schema for deleting an agent run by ID."""

    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    agent_run_id: Annotated[Optional[str], Field(description='Agent run ID to delete', default=None)] = None


class CreateAgentRunsRequestSchema(BaseRequestSchema):
    """Request schema for bulk creating agent runs."""

    tenant_id: Annotated[Optional[str], Field(description='Tenant ID', default=None)] = None
    bu_id: Annotated[Optional[str], Field(description='Business Unit ID', default=None)] = None
    agent_runs: Annotated[List[CreateAgentRunRequestSchema], Field(description='List of agent runs to create')]


# ── API response schemas ─────────────────────────────────────────────


class CreateAgentRunResponseSchema(BaseResponseSchema):
    """Response schema for creating a single agent run."""

    agent_run: AgentRunSchema


class CreateAgentRunsResponseSchema(BaseResponseSchema):
    """Response schema for bulk creating agent runs."""

    agent_runs: List[AgentRunSchema]


class UpdateAgentRunResponseSchema(BaseResponseSchema):
    """Response schema for updating an agent run."""

    agent_run: AgentRunSchema


class GetAgentRunByIdResponseSchema(BaseResponseSchema):
    """Response schema for getting an agent run by ID."""

    agent_run: Optional[AgentRunSchema] = None

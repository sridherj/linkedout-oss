# SPDX-License-Identifier: Apache-2.0
"""Agent run entity for tracking async agent executions."""
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = JSON  # Fallback to JSON for SQLite testing

from common.entities.base_entity import BaseEntity
from common.entities.tenant_bu_mixin import TenantBuMixin
from shared.common.nanoids import Nanoid


class AgentRunEntity(TenantBuMixin, BaseEntity):
    """
    Entity for tracking async agent executions.

    Scoped by: Tenant and Business Unit.

    Tracks the lifecycle of an agent run from invocation to completion,
    including LLM metrics for cost and performance analysis.

    Attributes:
        agent_type: Type of agent (e.g. TASK_SUMMARIZER).
        status: Current status (PENDING, RUNNING, COMPLETED, FAILED).
        input_params: JSON input parameters for the agent run.
        output: JSON output from the agent run.
        error_message: Error message if the run failed.
        started_at: When the agent started executing.
        completed_at: When the agent finished executing.
        llm_input: The processed input sent to the LLM.
        llm_output: The structured response from the LLM.
        llm_cost_usd: Cost of the LLM call in USD.
        llm_latency_ms: Time taken for the LLM call in milliseconds.
        llm_metadata: Model name, token counts, provider info.
    """

    __tablename__ = 'agent_run'

    id_prefix = 'arn'

    id = mapped_column(
        String,
        primary_key=True,
        default=lambda: Nanoid.make_timestamped_id('arn'),
        comment='Unique identifier for the agent run',
    )

    agent_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment='Type of agent (e.g. TASK_SUMMARIZER)',
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='PENDING',
        comment='Current status: PENDING, RUNNING, COMPLETED, FAILED',
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='When the agent started executing',
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment='When the agent finished executing',
    )
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment='Error message if the run failed',
    )
    input_params: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        comment='JSON input parameters for the agent run',
    )
    output: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        comment='JSON output from the agent run',
    )

    # LLM tracking fields
    llm_input: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        comment='The processed input sent to the LLM',
    )
    llm_output: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        comment='The structured response from the LLM',
    )
    llm_cost_usd: Mapped[float] = mapped_column(
        Float,
        nullable=True,
        comment='Cost of the LLM call in USD',
    )
    llm_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment='Time taken for the LLM call in milliseconds',
    )
    llm_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=True,
        comment='Model name, token counts, provider info',
    )

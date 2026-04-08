# SPDX-License-Identifier: Apache-2.0
"""Registry-based agent executor with lifecycle management."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional, Type

from common.schemas.agent_run_schema import AgentRunStatus
from common.services.agent_run_service import AgentRunService
from common.services.base_agent import BaseAgent
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager
from shared.utilities.logger import get_logger

logger = get_logger(__name__)

# Module-level registry: agent_type -> agent class
_AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}


def register_agent(agent_type: str, agent_class: Type[BaseAgent]) -> None:
    """
    Register an agent class for a given agent type.

    Args:
        agent_type: String identifier for the agent type.
        agent_class: The BaseAgent subclass to register.
    """
    _AGENT_REGISTRY[agent_type] = agent_class
    logger.info(f'Registered agent: {agent_type} -> {agent_class.__name__}')


def get_registered_agent(agent_type: str) -> Optional[Type[BaseAgent]]:
    """
    Look up a registered agent class by type.

    Args:
        agent_type: String identifier for the agent type.

    Returns:
        The registered agent class, or None if not found.
    """
    return _AGENT_REGISTRY.get(agent_type)


def execute_agent(
    tenant_id: str,
    bu_id: str,
    agent_type: str,
    input_params: Optional[dict] = None,
    agent_run_id: Optional[str] = None,
) -> str:
    """
    Execute an agent with full status tracking.

    Two modes:

    1. **Pre-created record** (``agent_run_id`` provided): The AgentRun
       record already exists. Skips creation, goes straight to RUNNING.
    2. **Self-managed** (``agent_run_id`` is None): Creates the AgentRun
       record internally.

    Flow:
        1. Create or reuse agent_run record, update to RUNNING.
        2. Execute agent in a fresh session.
        3. Update to COMPLETED with LLM metrics (or FAILED on error).

    Args:
        tenant_id: Tenant ID.
        bu_id: Business unit ID.
        agent_type: Type of agent to execute.
        input_params: Agent-specific parameters.
        agent_run_id: If provided, reuse this existing AgentRun record.

    Returns:
        The agent_run_id.

    Raises:
        ValueError: If the agent_type is not registered.
    """
    try:
        # 1. Create AgentRun record (if needed) and update to RUNNING
        with db_session_manager.get_session(DbSessionType.WRITE) as session:
            service = AgentRunService(session)
            if agent_run_id is None:
                agent_run_schema = service.create_agent_run(
                    tenant_id=tenant_id,
                    bu_id=bu_id,
                    agent_type=agent_type,
                    input_params=input_params,
                )
                agent_run_id = agent_run_schema.id
            service.update_status(
                tenant_id=tenant_id,
                bu_id=bu_id,
                agent_run_id=agent_run_id,
                status=AgentRunStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
            )

        # 2. Execute agent in a fresh session
        agent_class = get_registered_agent(agent_type)
        if agent_class is None:
            raise ValueError(f'Unknown agent type: {agent_type}')

        with db_session_manager.get_session(DbSessionType.WRITE) as session:
            agent = agent_class(session)
            agent.run(
                tenant_id=tenant_id,
                bu_id=bu_id,
                agent_run_id=agent_run_id,
                **(input_params or {}),
            )
            llm_metrics = agent.get_llm_metrics()

        # 3. Update to COMPLETED with LLM metrics
        with db_session_manager.get_session(DbSessionType.WRITE) as session:
            service = AgentRunService(session)
            service.update_status(
                tenant_id=tenant_id,
                bu_id=bu_id,
                agent_run_id=agent_run_id,
                status=AgentRunStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
                llm_metrics=llm_metrics,
            )

        logger.info(f'Agent run {agent_run_id} completed successfully')
        return agent_run_id

    except Exception as e:
        logger.error(f'Agent run {agent_run_id} failed: {e}')
        if agent_run_id:
            try:
                with db_session_manager.get_session(DbSessionType.WRITE) as session:
                    service = AgentRunService(session)
                    service.update_status(
                        tenant_id=tenant_id,
                        bu_id=bu_id,
                        agent_run_id=agent_run_id,
                        status=AgentRunStatus.FAILED,
                        error_message=str(e),
                        completed_at=datetime.now(timezone.utc),
                    )
            except Exception as update_error:
                logger.error(f'Failed to update agent run status: {update_error}')
        raise

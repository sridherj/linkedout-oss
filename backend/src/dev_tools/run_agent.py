# SPDX-License-Identifier: Apache-2.0
"""Thin wrapper to import agent modules, trigger registration, and execute an agent."""
import sys

import click

from shared.utilities.logger import get_logger

logger = get_logger(__name__)


def run_agent(agent_name: str, tenant_id: str, bu_id: str) -> None:
    """Import agent modules to trigger registration, then execute the named agent."""
    from common.services.agent_executor_service import execute_agent, get_registered_agent

    agent_class = get_registered_agent(agent_name)
    if agent_class is None:
        click.echo(f'Error: Unknown agent "{agent_name}". Use "agent list" to see available agents.')
        sys.exit(1)

    logger.info(f'Executing agent: {agent_name} (tenant={tenant_id}, bu={bu_id})')
    agent_run_id = execute_agent(
        tenant_id=tenant_id,
        bu_id=bu_id,
        agent_type=agent_name,
    )
    click.echo(f'Agent run completed: {agent_run_id}')

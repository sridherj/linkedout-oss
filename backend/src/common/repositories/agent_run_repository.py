# SPDX-License-Identifier: Apache-2.0
"""Repository layer for AgentRun entity."""
from typing import List

from common.entities.agent_run_entity import AgentRunEntity
from common.repositories.base_repository import BaseRepository, FilterSpec
from common.schemas.agent_run_schema import AgentRunSortByFields


class AgentRunRepository(
    BaseRepository[AgentRunEntity, AgentRunSortByFields]
):
    """
    Repository for AgentRun entity database operations.

    Inherits common CRUD operations from BaseRepository.

    Filters:
    - agent_type: Exact match
    - status: Exact match
    """

    _entity_class = AgentRunEntity
    _default_sort_field = 'created_at'
    _entity_name = 'agent_run'

    def _get_filter_specs(self) -> List[FilterSpec]:
        """Return filter specifications for agent runs."""
        return [
            FilterSpec('agent_type', 'eq'),
            FilterSpec('status', 'eq'),
        ]

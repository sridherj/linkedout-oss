# SPDX-License-Identifier: Apache-2.0
"""Base context for agent execution."""
from pydantic import BaseModel, ConfigDict


class BaseAgentContext(BaseModel):
    """
    Base context for agent execution.

    Provides tenant and BU scoping. Frozen to prevent accidental mutation.
    Subclasses can add agent-specific context fields.
    """

    model_config = ConfigDict(frozen=True)

    tenant_id: str
    bu_id: str

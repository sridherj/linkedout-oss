# SPDX-License-Identifier: Apache-2.0
"""Interface for LLM client user/agent context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class LLMClientUser(ABC):
    """
    Interface for the consumer of the LLM Client.

    Implementations provide identity and context for LLM interactions,
    enabling tracking, cost attribution, and session management.

    Subclasses must implement get_agent_id() and get_session_id() to
    provide the necessary identity information for tracing.
    """

    @abstractmethod
    def get_agent_id(self) -> str:
        """
        Return the unique identifier for the agent/service.

        Returns:
            A unique string identifying the agent or service making
            the LLM call. Used for tracking and cost attribution.
        """
        pass

    @abstractmethod
    def get_session_id(self) -> Optional[str]:
        """
        Return the current session ID, if any.

        Returns:
            The session ID for grouping related LLM calls, or None
            if no session context exists.
        """
        pass

    def record_llm_cost(
        self,
        cost_usd: float,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Record LLM usage cost in the application database.

        This is an optional hook that implementations can override to
        persist cost information for billing or analytics.

        Args:
            cost_usd: The cost of the LLM call in US dollars.
            metadata: Additional metadata about the call including
                tokens used, model name, latency, etc.
        """
        pass


class SystemUser(LLMClientUser):
    """Lightweight LLMClientUser for callers that don't extend BaseAgent."""

    def __init__(self, agent_id: str):
        self._agent_id = agent_id

    def get_agent_id(self) -> str:
        return self._agent_id

    def get_session_id(self) -> Optional[str]:
        return None

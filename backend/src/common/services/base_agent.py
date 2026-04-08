# SPDX-License-Identifier: Apache-2.0
"""Base class for all AI agents."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

import pydantic
from sqlalchemy.orm import Session

from shared.config import get_config
from shared.utilities.logger import get_logger
from utilities.llm_manager.llm_client import LLMClient
from utilities.llm_manager.llm_client_user import LLMClientUser
from utilities.llm_manager.llm_factory import LLMFactory
from utilities.llm_manager.llm_message import LLMMessage
from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider
from utilities.prompt_manager.prompt_factory import PromptFactory

logger = get_logger(__name__)


class BaseAgent(LLMClientUser, ABC):
    """
    Base class for AI agents.

    Consolidates shared boilerplate: LLM config, prompt loading, metrics
    collection, and agent identity.

    Subclasses must implement ``run()`` with their specific signature.
    """

    def __init__(self, session: Session, agent_id: Optional[str] = None):
        """
        Initialize the base agent.

        Args:
            session: SQLAlchemy database session.
            agent_id: Unique identifier for this agent type.
                      Defaults to the class name if not provided.
        """
        self._session: Session = session
        self._agent_id = agent_id or self.__class__.__name__
        self._llm_input: Optional[dict] = None
        self._llm_metrics: Dict[str, Any] = {}

        logger.debug(f'Initialized {self.__class__.__name__}')

    def get_agent_id(self) -> str:
        """Return the unique identifier for the agent."""
        return self._agent_id

    def get_session_id(self) -> Optional[str]:
        """Return the current session ID (None for background agents)."""
        return None

    def record_llm_cost(
        self, cost_usd: float, metadata: Dict[str, Any]
    ) -> None:
        """Combine agent-side llm_input with client-side llm_output and metrics."""
        from fastapi.encoders import jsonable_encoder

        self._llm_metrics = {
            'llm_input': jsonable_encoder(self._llm_input),
            'llm_output': metadata.get('llm_output'),
            'llm_cost_usd': cost_usd,
            'llm_latency_ms': metadata.get('latency_ms'),
            'llm_metadata': {
                k: v for k, v in metadata.items() if k != 'llm_output'
            },
        }

    def get_llm_metrics(self) -> Dict[str, Any]:
        """Return captured LLM metrics after run() completes."""
        return self._llm_metrics

    def _create_llm_client(self) -> LLMClient:
        """Create a standard LLM client with config from settings."""
        settings = get_config()
        llm_config = LLMConfig(
            provider=settings.llm.provider or LLMProvider.OPENAI,
            model_name=settings.llm.model,
            api_key=settings.llm_api_key or settings.openai_api_key,
            api_base=settings.llm_api_base,
            api_version=settings.llm_api_version,
            enable_tracing=settings.langfuse_enabled,
        )
        return LLMFactory.create_client(self, llm_config)

    def _load_prompt(self, prompt_name: str):
        """Load a prompt by name via PromptFactory."""
        return PromptFactory.create_from_env().get(prompt_name)

    def _call_llm(
        self,
        prompt_name: str,
        variables: dict,
        response_model: Type[pydantic.BaseModel],
    ) -> pydantic.BaseModel:
        """
        Full LLM call flow.

        Loads the prompt, builds the message, calls the LLM with structured
        output, and captures llm_input (variables) for metrics.

        Args:
            prompt_name: Name of the prompt to load.
            variables: Template variables to fill in the prompt.
            response_model: Pydantic model for structured response parsing.

        Returns:
            Parsed response as a Pydantic model instance.
        """
        client = self._create_llm_client()
        prompt = self._load_prompt(prompt_name)
        llm_message = LLMMessage.from_prompt(prompt, variables=variables)
        self._llm_input = variables
        response = client.call_llm_structured(llm_message, response_model)
        return response

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """
        Execute the agent's main logic.

        Subclasses must implement this with their specific parameters.
        """
        ...

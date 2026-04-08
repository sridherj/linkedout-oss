# SPDX-License-Identifier: Apache-2.0
"""Pydantic schemas for LLM Manager configuration and data models."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Optional

from pydantic import BaseModel, Field, SecretStr, ConfigDict


class LLMProvider(StrEnum):
    """Supported LLM Providers."""

    OPENAI = 'openai'
    AZURE_OPENAI = 'azure_openai'
    GROQ = 'groq'
    GEMINI = 'gemini'


class LLMConfig(BaseModel):
    """
    Configuration for LLM Client.

    Contains all settings needed to initialize an LLM client including
    provider credentials, model parameters, and tracing configuration.

    Attributes:
        provider: The LLM provider to use.
        model_name: Name of the model (e.g., 'gpt-4', 'gpt-3.5-turbo').
        api_key: API key for authentication (stored securely).
        api_base: Base URL for API calls (required for Azure).
        api_version: API version (required for Azure).
        temperature: Sampling temperature (0.0 to 2.0).
        max_tokens: Maximum tokens in the response.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts on failure.
        langfuse_public_key: Langfuse public key for tracing.
        langfuse_secret_key: Langfuse secret key for tracing.
        langfuse_host: Langfuse API host URL.
        enable_tracing: Whether to enable Langfuse tracing.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_default=True,
    )

    provider: Annotated[
        LLMProvider,
        Field(description="The LLM provider to use")
    ]
    model_name: Annotated[
        str,
        Field(description="Name of the model (e.g., 'gpt-4')")
    ]
    api_key: Annotated[
        Optional[SecretStr],
        Field(default=None, description="API key for authentication")
    ]
    api_base: Annotated[
        Optional[str],
        Field(default=None, description="Base URL for API calls")
    ]
    api_version: Annotated[
        Optional[str],
        Field(default=None, description="API version (required for Azure)")
    ]
    temperature: Annotated[
        float,
        Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    ]
    max_tokens: Annotated[
        Optional[int],
        Field(default=None, gt=0, description="Maximum tokens in response")
    ]
    timeout: Annotated[
        int,
        Field(default=120, gt=0, description="Request timeout in seconds")
    ]
    max_retries: Annotated[
        int,
        Field(default=2, ge=0, description="Number of retry attempts")
    ]

    # Langfuse Configuration
    langfuse_public_key: Annotated[
        Optional[str],
        Field(default=None, description="Langfuse public key for tracing")
    ]
    langfuse_secret_key: Annotated[
        Optional[SecretStr],
        Field(default=None, description="Langfuse secret key for tracing")
    ]
    langfuse_host: Annotated[
        Optional[str],
        Field(default=None, description="Langfuse API host URL")
    ]
    enable_tracing: Annotated[
        bool,
        Field(default=True, description="Whether to enable Langfuse tracing")
    ]


class LLMMetrics(BaseModel):
    """
    Metrics for an LLM call.

    Captures usage statistics and performance metrics for a single
    LLM API call.

    Attributes:
        request_id: Unique identifier for the request.
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Total tokens used (prompt + completion).
        cost_usd: Estimated cost in US dollars.
        latency_ms: Total request latency in milliseconds.
        ttft_ms: Time to first token in milliseconds (streaming only).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: Annotated[
        str,
        Field(description="Unique identifier for the request")
    ]
    prompt_tokens: Annotated[
        int,
        Field(default=0, ge=0, description="Number of tokens in the prompt")
    ]
    completion_tokens: Annotated[
        int,
        Field(default=0, ge=0, description="Number of tokens in completion")
    ]
    total_tokens: Annotated[
        int,
        Field(default=0, ge=0, description="Total tokens used")
    ]
    cost_usd: Annotated[
        float,
        Field(default=0.0, ge=0.0, description="Estimated cost in USD")
    ]
    latency_ms: Annotated[
        float,
        Field(default=0.0, ge=0.0, description="Total latency in milliseconds")
    ]
    ttft_ms: Annotated[
        Optional[float],
        Field(default=None, ge=0.0, description="Time to first token in ms")
    ]


class LLMMessageMetadata(BaseModel):
    """
    Metadata for an LLM message.

    Contains tracing and identification information for correlating
    LLM calls across distributed systems.

    Attributes:
        request_id: Unique identifier for the request.
        session_id: Session identifier for grouping related calls.
        trace_id: Distributed tracing trace ID.
        span_id: Distributed tracing span ID.
        user_id: User identifier for attribution.
        llm_metrics: Optional metrics from a completed call.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    request_id: Annotated[
        str,
        Field(description="Unique identifier for the request")
    ]
    session_id: Annotated[
        Optional[str],
        Field(default=None, description="Session ID for grouping calls")
    ]
    trace_id: Annotated[
        Optional[str],
        Field(default=None, description="Distributed tracing trace ID")
    ]
    span_id: Annotated[
        Optional[str],
        Field(default=None, description="Distributed tracing span ID")
    ]
    user_id: Annotated[
        Optional[str],
        Field(default=None, description="User identifier for attribution")
    ]
    llm_metrics: Annotated[
        Optional[LLMMetrics],
        Field(default=None, description="Metrics from a completed call")
    ]


class LLMToolResponse(BaseModel):
    """Response from an LLM call that may include tool calls."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = []  # Each: {"id": str, "name": str, "args": dict}

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)

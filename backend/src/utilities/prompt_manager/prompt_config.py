# SPDX-License-Identifier: Apache-2.0
"""Configuration schema for PromptManager."""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class PromptManagerConfig(BaseModel):
    """
    Configuration for PromptManager.

    Controls which store to use, caching behavior, and provider
    credentials. The environment field is used to derive the
    Langfuse label for fetching.
    """

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    use_local_files: Annotated[bool, Field(default=False)]
    prompts_directory: Annotated[str, Field(default='prompts')]
    environment: Annotated[
        str,
        Field(default='production', description='Maps to Langfuse label'),
    ]
    cache_ttl_seconds: Annotated[int, Field(default=300, ge=0)]

    langfuse_public_key: Annotated[Optional[SecretStr], Field(default=None)]
    langfuse_secret_key: Annotated[Optional[SecretStr], Field(default=None)]
    langfuse_host: Annotated[Optional[str], Field(default=None)]

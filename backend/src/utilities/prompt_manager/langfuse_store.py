# SPDX-License-Identifier: Apache-2.0
"""Langfuse prompt store implementations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import SecretStr
from langfuse import Langfuse

from utilities.prompt_manager.exceptions import (
    PromptConfigurationError,
    PromptNotFoundError,
    PromptStoreError,
)
from utilities.prompt_manager.prompt_schemas import (
    ChatMessage,
    PromptSchema,
    PromptType,
)



class LangfusePromptStore:
    """
    Prompt store that retrieves prompts from Langfuse.

    Used for dev/prod environments. Supports versioning and labels.
    """

    def __init__(
        self,
        public_key: Optional[SecretStr] = None,
        secret_key: Optional[SecretStr] = None,
        host: Optional[str] = None,
        environment: str = 'production',
    ) -> None:
        """
        Initialize LangfusePromptStore.

        Args:
            public_key: Langfuse public key.
            secret_key: Langfuse secret key.
            host: Langfuse host URL.
            environment: Environment name (used as default label).

        Raises:
            PromptConfigurationError: If credentials are missing.
        """
        if not public_key or not secret_key:
            raise PromptConfigurationError(
                'Langfuse credentials are required.'
            )

        self._client: Langfuse = Langfuse(
            public_key=public_key.get_secret_value(),
            secret_key=secret_key.get_secret_value(),
            host=host,
        )
        self._environment: str = environment

    def get(
        self,
        prompt_key: str,
        *,
        label: Optional[str] = None,
        version: Optional[int] = None,
    ) -> PromptSchema:
        """
        Retrieve a prompt from Langfuse.

        Args:
            prompt_key: Stable internal identifier.
            label: Label to fetch (defaults to mapped environment).
            version: Specific version to fetch.

        Returns:
            PromptSchema converted from Langfuse prompt.

        Raises:
            PromptNotFoundError: If prompt does not exist.
            PromptStoreError: If retrieval fails.
        """
        prompt = _fetch_langfuse_prompt(
            self._client,
            prompt_key,
            label or _get_env_label(self._environment),
            version,
        )
        return _convert_langfuse_prompt(prompt_key, prompt)


class LangfusePromptStoreTooling:
    """
    Tooling operations for Langfuse prompt store.

    Provides push/pull operations for CLI utilities to synchronize
    prompts between local files and Langfuse.
    """

    def __init__(
        self,
        public_key: Optional[SecretStr] = None,
        secret_key: Optional[SecretStr] = None,
        host: Optional[str] = None,
    ) -> None:
        """
        Initialize LangfusePromptStoreTooling.

        Args:
            public_key: Langfuse public key.
            secret_key: Langfuse secret key.
            host: Langfuse host URL.

        Raises:
            PromptConfigurationError: If credentials are missing.
        """
        if not public_key or not secret_key:
            raise PromptConfigurationError(
                'Langfuse credentials are required.'
            )

        self._client = Langfuse(
            public_key=public_key.get_secret_value(),
            secret_key=secret_key.get_secret_value(),
            host=host or _DEFAULT_LANGFUSE_HOST,
        )

    def push(
        self,
        prompt: PromptSchema,
        *,
        labels: Optional[List[str]] = None,
    ) -> PromptSchema:
        """
        Push a prompt to Langfuse.

        Args:
            prompt: Prompt to push.
            labels: Labels to assign (defaults to mapped environment).

        Returns:
            Updated PromptSchema with Langfuse-assigned version.
        """
        from shared.config import get_config
        target_labels = labels or [_get_env_label(get_config().environment)]

        prompt_payload = _prompt_payload(prompt)
        try:
            created = self._client.create_prompt(
                name=prompt.prompt_key,
                type=prompt.prompt_type.value,
                prompt=prompt_payload,
                labels=target_labels,
                config=prompt.config,
            )
        except Exception as exc:
            raise PromptStoreError(
                'Failed to push prompt to Langfuse.'
            ) from exc

        return _convert_langfuse_prompt(prompt.prompt_key, created)

    def pull(
        self,
        prompt_key: str,
        *,
        label: Optional[str] = None,
        version: Optional[int] = None,
    ) -> PromptSchema:
        """
        Pull a prompt from Langfuse.

        Args:
            prompt_key: Stable internal identifier.
            label: Label to pull.
            version: Specific version to pull.

        Returns:
            PromptSchema from the remote store.
        """
        from shared.config import get_config
        target_label = label or _get_env_label(get_config().environment)

        prompt = _fetch_langfuse_prompt(
            self._client,
            prompt_key,
            target_label,
            version,
        )
        return _convert_langfuse_prompt(prompt_key, prompt)


def _get_env_label(environment: str) -> str:
    """
    Map environment name to Langfuse label.

    Args:
        environment: Environment name (local, dev, staging, prod).

    Returns:
        Mapped Langfuse label.
    """
    env_map = {
        'local': 'staging',
        'dev': 'staging',
        'test': 'staging',
        'staging': 'staging',
        'prod': 'production',
        'production': 'production',
    }
    return env_map.get(environment, 'production')


def _prompt_payload(prompt: PromptSchema) -> Any:
    """
    Convert PromptSchema into Langfuse prompt payload.

    Args:
        prompt: PromptSchema to serialize.

    Returns:
        Prompt payload for Langfuse API.
    """
    if prompt.prompt_type == PromptType.TEXT:
        return prompt.content
    return [
        {'role': msg.role, 'content': msg.content}
        for msg in prompt.content
    ]


def _fetch_langfuse_prompt(
    client: Langfuse,
    prompt_key: str,
    label: Optional[str],
    version: Optional[int],
) -> Any:
    """
    Fetch a prompt from Langfuse with error handling.

    Args:
        client: Langfuse client instance.
        prompt_key: Stable internal identifier.
        label: Optional label for selection.
        version: Optional version for selection.

    Returns:
        Langfuse prompt object.
    """
    try:
        return client.get_prompt(
            prompt_key,
            label=label,
            version=version,
        )
    except Exception as exc:
        raise PromptNotFoundError(
            prompt_key,
            label=label,
        ) from exc


def _convert_langfuse_prompt(prompt_key: str, prompt_obj: Any) -> PromptSchema:
    """
    Convert Langfuse prompt object to PromptSchema.

    Args:
        prompt_key: Prompt key.
        prompt_obj: Langfuse prompt object.

    Returns:
        PromptSchema representation.
    """
    prompt_content = getattr(prompt_obj, 'prompt', None)
    prompt_type = getattr(prompt_obj, 'type', None)
    labels = getattr(prompt_obj, 'labels', None) or []
    version = getattr(prompt_obj, 'version', None)
    config = getattr(prompt_obj, 'config', None)

    if prompt_type:
        prompt_type_enum = PromptType(prompt_type)
    else:
        prompt_type_enum = (
            PromptType.CHAT
            if isinstance(prompt_content, list)
            else PromptType.TEXT
        )

    if prompt_type_enum == PromptType.TEXT:
        return PromptSchema(
            prompt_key=prompt_key,
            prompt_type=prompt_type_enum,
            content=str(prompt_content),
            labels=labels,
            version=version,
            config=config,
        )

    messages = [
        ChatMessage(role=item['role'], content=item['content'])
        for item in prompt_content or []
    ]
    return PromptSchema(
        prompt_key=prompt_key,
        prompt_type=prompt_type_enum,
        content=messages,
        labels=labels,
        version=version,
        config=config,
    )

# SPDX-License-Identifier: Apache-2.0
"""Prompt store protocols for runtime and tooling."""

from __future__ import annotations

from typing import List, Optional, Protocol

from utilities.prompt_manager.prompt_schemas import PromptSchema


class PromptStore(Protocol):
    """
    Protocol for prompt storage backends.

    Implementations must provide a get() method that retrieves prompts
    by their stable internal identifier, with optional label filtering.
    """

    def get(
        self,
        prompt_key: str,
        *,
        label: Optional[str] = None,
        version: Optional[int] = None,
    ) -> PromptSchema:
        """
        Retrieve a prompt by its key.

        Args:
            prompt_key: Stable internal identifier.
            label: Optional label to fetch.
            version: Optional specific version to fetch.

        Returns:
            PromptSchema with the prompt content and metadata.

        Raises:
            PromptNotFoundError: If prompt does not exist or label doesn't match.
            PromptStoreError: If retrieval fails.
        """


class PromptStoreTooling(Protocol):
    """
    Protocol for prompt store tooling operations.

    These methods are used by CLI utilities for push/pull operations,
    not by application runtime code.
    """

    def push(
        self,
        prompt: PromptSchema,
        *,
        labels: Optional[List[str]] = None,
    ) -> PromptSchema:
        """
        Push a prompt to the remote store.

        Args:
            prompt: Prompt to push.
            labels: Labels to assign to this version.

        Returns:
            Updated PromptSchema with provider-assigned version.
        """

    def pull(
        self,
        prompt_key: str,
        *,
        label: Optional[str] = None,
        version: Optional[int] = None,
    ) -> PromptSchema:
        """
        Pull a prompt from the remote store.

        Args:
            prompt_key: Stable internal identifier.
            label: Label to pull.
            version: Specific version to pull.

        Returns:
            PromptSchema from the remote store.
        """

# SPDX-License-Identifier: Apache-2.0
"""Local file prompt store implementation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from utilities.prompt_manager.exceptions import (
    PromptNotFoundError,
    PromptStoreError,
)
from utilities.prompt_manager.prompt_schemas import (
    ChatMessage,
    PromptMetadata,
    PromptSchema,
    PromptType,
)


class LocalFilePromptStore:
    """
    Prompt store that reads from local files.

    Used for local development and testing. Prompts are stored in the
    prompts/ directory with JSONC metadata files (supports comments).
    """

    _prompts_directory: Path

    def __init__(self, prompts_directory: str = 'prompts') -> None:
        """
        Initialize LocalFilePromptStore.

        Args:
            prompts_directory: Path to prompts folder.

        Raises:
            ValueError: If prompts directory does not exist.
        """
        self._prompts_directory = Path(prompts_directory)
        if not self._prompts_directory.exists():
            raise ValueError(
                f'Prompts directory not found: {prompts_directory}'
            )

    def get(
        self,
        prompt_key: str,
        *,
        label: Optional[str] = None,
        version: Optional[int] = None,
    ) -> PromptSchema:
        """
        Retrieve a prompt from local files.

        Args:
            prompt_key: Stable internal identifier.
            label: If provided, verified against prompt's labels.
            version: Ignored for local files.

        Returns:
            PromptSchema loaded from local files.

        Raises:
            PromptNotFoundError: If prompt files do not exist or label
                mismatch.
        """
        _ = version
        metadata_path = self._get_metadata_path(prompt_key)
        if not metadata_path.exists():
            raise PromptNotFoundError(prompt_key)

        metadata = self._load_metadata(metadata_path)
        if metadata.prompt_key != prompt_key:
            raise PromptNotFoundError(prompt_key)

        if label and label not in metadata.labels:
            raise PromptNotFoundError(
                prompt_key,
                f"Label '{label}' not found."
            )

        content_path = metadata_path.parent / metadata.content_file
        if not content_path.exists():
            raise PromptNotFoundError(prompt_key)

        if metadata.prompt_type == PromptType.TEXT:
            content_text = content_path.read_text()
            return PromptSchema(
                prompt_key=metadata.prompt_key,
                prompt_type=metadata.prompt_type,
                content=content_text,
                labels=metadata.labels,
                config=metadata.config,
                variables=self._extract_variables(
                    metadata.prompt_type,
                    content_text,
                ),
            )

        messages = self._load_jsonc(content_path)
        chat_messages = [ChatMessage(**item) for item in messages]
        return PromptSchema(
            prompt_key=metadata.prompt_key,
            prompt_type=metadata.prompt_type,
            content=chat_messages,
            labels=metadata.labels,
            config=metadata.config,
            variables=self._extract_variables(
                metadata.prompt_type,
                chat_messages,
            ),
        )

    def _get_metadata_path(self, prompt_key: str) -> Path:
        """
        Resolve metadata file path for a prompt key.

        Args:
            prompt_key: Stable internal identifier.

        Returns:
            Path to metadata file.
        """
        return self._prompts_directory / f'{prompt_key}.meta.jsonc'

    def _load_metadata(self, file_path: Path) -> PromptMetadata:
        """
        Load prompt metadata from a JSONC file.

        Args:
            file_path: Path to JSONC metadata file.

        Returns:
            Parsed PromptMetadata instance.

        Raises:
            PromptStoreError: If parsing fails.
        """
        data = self._load_jsonc(file_path)
        try:
            return PromptMetadata(**data)
        except Exception as exc:
            raise PromptStoreError(
                f'Failed to parse metadata: {file_path}'
            ) from exc

    def _load_jsonc(self, file_path: Path) -> Any:
        """
        Load and parse a JSONC file (JSON with comments).

        Args:
            file_path: Path to JSONC file.

        Returns:
            Parsed JSON data.

        Raises:
            PromptStoreError: If parsing fails.
        """
        try:
            import jsonc_parser.parser as jsonc
        except Exception as exc:
            raise PromptStoreError(
                'jsonc-parser dependency is required for JSONC files.'
            ) from exc

        try:
            content = file_path.read_text()
            parsed = jsonc.JsoncParser.parse_str(content)
            if not isinstance(parsed, dict) and not isinstance(parsed, list):
                raise ValueError('Invalid JSONC content type.')
            return parsed
        except Exception as exc:
            raise PromptStoreError(
                f'Failed to parse JSONC file: {file_path}'
            ) from exc

    def _extract_variables(
        self,
        prompt_type: PromptType,
        content: Any,
    ) -> List[str]:
        """
        Extract variables using schema logic.

        Args:
            prompt_type: Type of prompt.
            content: Content string or list of messages.

        Returns:
            List of variable names.
        """
        # Create a temporary schema to reuse variable extraction logic
        # without full validation overhead
        if prompt_type == PromptType.TEXT:
            temp = PromptSchema(
                prompt_key='temp',
                prompt_type=prompt_type,
                content=str(content),  # Ensure string
            )
        else:
            # content is already a list of ChatMessage objects
            temp = PromptSchema(
                prompt_key='temp',
                prompt_type=prompt_type,
                content=content if isinstance(content, list) else [],
            )
        return temp.variables

    def _write_jsonc(self, file_path: Path, data: Dict[str, Any]) -> None:
        """
        Write JSON data to a JSONC file.

        Args:
            file_path: Path to JSONC file.
            data: Data to serialize.
        """
        serialized = json.dumps(data, indent=2)
        file_path.write_text(serialized)

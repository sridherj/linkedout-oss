# SPDX-License-Identifier: Apache-2.0
"""Prompt Manager CLI utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from pydantic import SecretStr

from shared.config import get_config
from utilities.prompt_manager.exceptions import PromptStoreError
from utilities.prompt_manager.langfuse_store import (
    LangfusePromptStoreTooling,
)
from utilities.prompt_manager.local_file_store import LocalFilePromptStore
from utilities.prompt_manager.prompt_schemas import (
    PromptMetadata,
    PromptSchema,
    PromptType,
)


@click.group()
def pm() -> None:
    """Prompt Manager CLI utilities."""


@pm.command()
@click.argument('prompt_key', required=False)
@click.option('--labels', '-l', help='Comma-separated labels')
@click.option('--all', 'push_all', is_flag=True, help='Push all prompts')
def push(
    prompt_key: Optional[str],
    labels: Optional[str],
    push_all: bool,
) -> None:
    """
    Push prompt(s) from local files to Langfuse.

    Creates a new version if the prompt already exists.
    """
    settings = get_config()
    prompts_directory = settings.prompts_directory
    tooling = _create_tooling()
    store = LocalFilePromptStore(prompts_directory=prompts_directory)
    label_list = _parse_csv(labels)
    success_count = 0
    fail_count = 0
    errors = []

    if push_all:
        metadata_files = _list_metadata_files(prompts_directory)
        click.secho(f"🚀 Pushing {len(metadata_files)} prompts to Langfuse...", fg='cyan', bold=True)
        
        for metadata_file in metadata_files:
            metadata = _load_metadata_jsonc(metadata_file)
            try:
                _push_single_prompt(
                    store,
                    tooling,
                    metadata.prompt_key,
                    label_list,
                    prompts_directory,
                )
                click.secho(f"  ✅ Pushed: {metadata.prompt_key}", fg='green')
                success_count += 1
            except Exception as e:
                click.secho(f"  ❌ Failed: {metadata.prompt_key} - {str(e)}", fg='red')
                fail_count += 1
                errors.append(f"{metadata.prompt_key}: {str(e)}")
        
        _print_summary("Push", success_count, fail_count, errors)
        return

    if not prompt_key:
        raise click.UsageError('Provide a prompt_key or use --all.')

    click.secho(f"🚀 Pushing prompt '{prompt_key}' to Langfuse...", fg='cyan')
    try:
        _push_single_prompt(
            store,
            tooling,
            prompt_key,
            label_list,
            prompts_directory,
        )
        click.secho(f"✅ Successfully pushed '{prompt_key}'", fg='green', bold=True)
    except Exception as e:
        click.secho(f"❌ Failed to push '{prompt_key}': {str(e)}", fg='red', bold=True)
        raise click.ClickException(str(e))


@pm.command()
@click.argument('prompt_key', required=False)
@click.option('--label', '-l', help='Label to pull')
@click.option('--version', '-v', type=int, help='Specific version to pull')
@click.option('--all', 'pull_all', is_flag=True, help='Pull all prompts')
def pull(
    prompt_key: Optional[str],
    label: Optional[str],
    version: Optional[int],
    pull_all: bool,
) -> None:
    """
    Pull prompt(s) from Langfuse to local files.

    Updates local content and metadata files.
    """
    settings = get_config()
    prompts_directory = settings.prompts_directory
    tooling = _create_tooling()
    success_count = 0
    fail_count = 0
    errors = []

    if pull_all:
        metadata_files = _list_metadata_files(prompts_directory)
        click.secho(f"📥 Pulling {len(metadata_files)} prompts from Langfuse...", fg='cyan', bold=True)
        
        for metadata_file in metadata_files:
            metadata = _load_metadata_jsonc(metadata_file)
            try:
                prompt = tooling.pull(
                    metadata.prompt_key,
                    label=label,
                    version=version,
                )
                _write_prompt_to_local(prompt, prompts_directory)
                click.secho(f"  ✅ Pulled: {metadata.prompt_key}", fg='green')
                success_count += 1
            except Exception as e:
                click.secho(f"  ❌ Failed: {metadata.prompt_key} - {str(e)}", fg='red')
                fail_count += 1
                errors.append(f"{metadata.prompt_key}: {str(e)}")
        
        _print_summary("Pull", success_count, fail_count, errors)
        return

    if not prompt_key:
        raise click.UsageError('Provide a prompt_key or use --all.')

    click.secho(f"📥 Pulling prompt '{prompt_key}' from Langfuse...", fg='cyan')
    try:
        prompt = tooling.pull(prompt_key, label=label, version=version)
        _write_prompt_to_local(prompt, prompts_directory)
        click.secho(f"✅ Successfully pulled '{prompt_key}'", fg='green', bold=True)
    except Exception as e:
        click.secho(f"❌ Failed to pull '{prompt_key}': {str(e)}", fg='red', bold=True)
        raise click.ClickException(str(e))


def _create_tooling() -> LangfusePromptStoreTooling:
    """
    Create Langfuse prompt tooling from environment variables.

    Returns:
        LangfusePromptStoreTooling instance.
    """
    settings = get_config()
    return LangfusePromptStoreTooling(
        public_key=(
            SecretStr(settings.langfuse_public_key)
            if settings.langfuse_public_key
            else None
        ),
        secret_key=(
            SecretStr(settings.langfuse_secret_key)
            if settings.langfuse_secret_key
            else None
        ),
        host=settings.langfuse_host,
    )


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    """
    Parse a comma-separated string into a list.

    Args:
        value: Comma-separated string.

    Returns:
        List of values or None if input is empty.
    """
    if not value:
        return None
    return [item.strip() for item in value.split(',') if item.strip()]


def _list_metadata_files(prompts_directory: str) -> List[Path]:
    """
    List all metadata files under prompts directory.

    Args:
        prompts_directory: Root prompts directory.

    Returns:
        List of metadata file paths.
    """
    base_dir = Path(prompts_directory)
    return list(base_dir.rglob('*.meta.jsonc'))


def _load_metadata_jsonc(file_path: Path) -> PromptMetadata:
    """
    Load prompt metadata from JSONC file.

    Args:
        file_path: Path to metadata file.

    Returns:
        Parsed PromptMetadata object.
    """
    try:
        import jsonc_parser.parser as jsonc
    except Exception as exc:
        raise PromptStoreError(
            'jsonc-parser dependency is required for JSONC files.'
        ) from exc

    content = file_path.read_text()
    data = jsonc.JsoncParser.parse_str(content)
    return PromptMetadata(**data)


def _push_single_prompt(
    store: LocalFilePromptStore,
    tooling: LangfusePromptStoreTooling,
    prompt_key: str,
    labels: Optional[List[str]],
    prompts_directory: str,
) -> None:
    """
    Push a single prompt and update metadata.

    Args:
        store: Local file prompt store.
        tooling: Langfuse tooling instance.
        prompt_key: Prompt key to push.
        labels: Labels to apply.
        prompts_directory: Prompts directory path.
    """
    prompt = store.get(prompt_key)
    pushed = tooling.push(prompt, labels=labels)
    _write_prompt_to_local(pushed, prompts_directory)


def _write_prompt_to_local(
    prompt: PromptSchema,
    prompts_directory: str,
) -> None:
    """
    Write a prompt to local files.

    Args:
        prompt: Prompt schema to write.
        prompts_directory: Prompts directory path.
    """
    metadata_path, content_path = _resolve_paths(
        prompts_directory,
        prompt.prompt_key,
        prompt.prompt_type,
    )
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    if prompt.prompt_type == PromptType.TEXT:
        content_path.write_text(str(prompt.content))
    else:
        content = [
            {'role': msg.role, 'content': msg.content}
            for msg in prompt.content
        ]
        content_path.write_text(json.dumps(content, indent=2))

    metadata = PromptMetadata(
        prompt_key=prompt.prompt_key,
        prompt_type=prompt.prompt_type,
        content_file=content_path.name,
        version=(
            str(prompt.version) if prompt.version is not None else None
        ),
        labels=prompt.labels,
        config=prompt.config,
    )
    _write_metadata(metadata_path, metadata)


def _resolve_paths(
    prompts_directory: str,
    prompt_key: str,
    prompt_type: PromptType,
) -> tuple[Path, Path]:
    """
    Resolve metadata and content file paths for a prompt.

    Args:
        prompts_directory: Prompts directory path.
        prompt_key: Prompt key to resolve.
        prompt_type: Prompt type to determine content extension.

    Returns:
        Tuple of (metadata_path, content_path).
    """
    base_dir = Path(prompts_directory) / prompt_key
    metadata_path = base_dir.with_suffix('.meta.jsonc')
    extension = '.md' if prompt_type == PromptType.TEXT else '.jsonc'
    content_path = base_dir.with_suffix(extension)
    return metadata_path, content_path


def _write_metadata(file_path: Path, metadata: PromptMetadata) -> None:
    """
    Write metadata to JSONC file.

    Args:
        file_path: Metadata file path.
        metadata: PromptMetadata to serialize.
    """
    data: Dict[str, Any] = metadata.model_dump()
    serialized = json.dumps(data, indent=2)
    file_path.write_text(serialized)


def _print_summary(
    action: str,
    success_count: int,
    fail_count: int,
    errors: List[str],
) -> None:
    """Print operation summary."""
    click.echo("")
    click.secho(f"📊 {action} Summary", bold=True, underline=True)
    click.secho(f"  ✅ Success: {success_count}", fg='green')
    
    if fail_count > 0:
        click.secho(f"  ❌ Failed:  {fail_count}", fg='red')
        click.echo("\nErrors:")
        for err in errors:
            click.secho(f"  - {err}", fg='red')
    
    click.echo("")
    if fail_count == 0:
        click.secho(f"✨ All {action.lower()} operations completed successfully!", fg='green', bold=True)
    else:
        click.secho(f"⚠️ {action} completed with some errors.", fg='yellow', bold=True)

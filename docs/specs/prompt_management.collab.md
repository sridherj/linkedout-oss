---
feature: prompt-management
module: src/utilities/prompt_manager
linked_files:
  - src/utilities/prompt_manager/prompt_manager.py
  - src/utilities/prompt_manager/prompt_factory.py
  - src/utilities/prompt_manager/prompt_config.py
  - src/utilities/prompt_manager/prompt_store.py
  - src/utilities/prompt_manager/local_file_store.py
  - src/utilities/prompt_manager/langfuse_store.py
  - src/utilities/prompt_manager/prompt_schemas.py
  - src/utilities/prompt_manager/cli.py
last_verified: 2026-03-25
version: 1
---

# Prompt Management

**Created:** 2026-03-25 — Backfilled from existing implementation

## Intent

Provide a provider-agnostic prompt management system where prompts can be loaded from local files or a remote store (Langfuse). The prompt source is switchable via configuration, and the system works offline without Langfuse.

## Behaviors

### PromptManager

- **Get prompt by key**: `manager.get(prompt_key)` retrieves a `PromptSchema` from the configured store. Optional `label` and `version` overrides are supported. Verify the returned schema is ready for compilation.

- **Store resolution**: When `use_local_files=True`, a `LocalFilePromptStore` is used. When `use_local_files=False`, a `LangfusePromptStore` is used. Verify the correct store is instantiated based on config.

### PromptFactory

- **Environment-based creation**: `PromptFactory.create_from_env()` reads configuration from environment/config and returns a configured PromptManager. Verify it creates the correct store type.

### PromptManagerConfig

- **Local file toggle**: `use_local_files` (bool, default False) controls whether prompts come from local files or Langfuse. Verify toggling this changes the store.

- **Prompts directory**: `prompts_directory` (default 'prompts') points to the local prompt files root. Verify prompts are loaded from this directory when local mode is on.

- **Environment mapping**: `environment` (default 'production') maps to the Langfuse label for fetching the correct prompt version. Verify different environments can fetch different prompt versions.

- **Cache TTL**: `cache_ttl_seconds` (default 300) controls how long prompts are cached. Verify cache behavior respects TTL.

### LocalFilePromptStore

- **File-based loading**: Loads prompts from the filesystem using the prompt key as a relative path. Supports both text (`.md`) and chat (`.jsonc`) prompt formats. Verify a prompt file at `prompts/agents/classifier.jsonc` is loadable via key `agents/classifier`.

### LangfusePromptStore

- **Remote loading**: Loads prompts from Langfuse using public/secret keys and host. The environment config maps to the Langfuse label. Verify prompts can be fetched when Langfuse is configured.

### PromptSchema

- **Template compilation**: `prompt.compile(**variables)` substitutes template variables. For text prompts, returns a string. For chat prompts, returns a list of message dicts. Verify variable substitution works correctly.

- **Bridge to LLMMessage**: `LLMMessage.from_prompt(prompt, variables=...)` creates an LLMMessage from a compiled prompt. Verify the bridge produces correct LangChain message format.

### CLI Commands

- **Prompt management CLI**: The `prompt` CLI group provides commands for listing, pushing, and pulling prompts. Verify commands are discoverable via `--help`.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Prompt source toggle | Config-driven use_local_files flag | Runtime switching | Simple, predictable — one source per deployment |
| 2026-03-25 | Prompt format | .md for text, .jsonc with meta sidecar for chat | Single format | Different use cases need different structures |
| 2026-03-25 | Store interface | Abstract PromptStore with get() method | Direct Langfuse SDK | Clean seam for testing and provider replacement |

## Not Included

- Prompt versioning in local files (Langfuse handles versions remotely)
- A/B testing of prompts
- Prompt validation or linting
- Automatic prompt migration between stores

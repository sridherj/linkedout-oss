---
feature: tracing
module: backend/src/shared/utilities, backend/src/utilities/llm_manager
linked_files:
  - backend/src/shared/utilities/langfuse_guard.py
  - backend/src/utilities/llm_manager/llm_client.py
  - backend/src/utilities/llm_manager/llm_schemas.py
  - backend/src/shared/config/settings.py
  - backend/src/utilities/prompt_manager/langfuse_store.py
version: 1
last_verified: "2026-04-09"
---

# Tracing (Langfuse)

**Created:** 2026-04-09 — Adapted from internal spec for OSS

## Intent

Provide optional LLM call tracing via Langfuse that is disabled by default in OSS. A guard module (`langfuse_guard.py`) intercepts all Langfuse imports so the app runs without the Langfuse SDK active unless explicitly enabled. When enabled, all LLM calls are traced with latency, token usage, and model metadata. When disabled, no tracing overhead is incurred and no Langfuse import errors occur.

## Behaviors

### Guard Module (OSS-Specific)

- **No-op by default**: `shared.utilities.langfuse_guard` provides drop-in replacements for `observe`, `get_client`, and `propagate_attributes`. When `langfuse_enabled` is False (the default), these return no-op decorators, a `_NoOpClient` stub, and a pass-through context manager respectively. Verify that importing and using the guard with `LANGFUSE_ENABLED=false` does not import the `langfuse` package.

- **All consumers use the guard**: Every file in `backend/src/` that previously imported from `langfuse` directly now imports from `shared.utilities.langfuse_guard` instead. The only files that import `langfuse` directly are the guard itself and `utilities/prompt_manager/langfuse_store.py` (which requires credentials at init time). Verify no other `from langfuse import` exists outside these two files.

- **_NoOpClient absorbs method chains**: The stub client supports `trace()`, `span()`, `generation()`, `flush()`, `start_as_current_observation()`, context manager protocol, and arbitrary `__getattr__` calls. All return `self` so chained calls like `client.trace().span().generation()` silently succeed. Verify no AttributeError is raised from consumer code when Langfuse is disabled.

- **Lazy imports**: The guard uses conditional imports inside `if _is_enabled()` blocks so the `langfuse` package is never loaded when disabled. This means the app starts without `langfuse` installed if tracing is off.

### Tracing Toggle

- **Config-driven enable**: `settings.langfuse_enabled` (default False) in `shared/config/settings.py` controls the global toggle. `LLMConfig.enable_tracing` (default True) controls per-client tracing. Both must be true for tracing to activate — the guard checks the global setting, and the LLM client checks its own config. Verify that setting either to False results in no Langfuse handler being created.

- **Independent of prompt source**: Tracing can be on while prompts come from local files, or off while prompts come from Langfuse. The prompt store (`langfuse_store.py`) imports `langfuse` directly and requires credentials at construction time, independent of the tracing toggle.

- **Graceful degradation**: When tracing is enabled but Langfuse credentials are missing (no public_key or secret_key), tracing is silently disabled with a warning log. Verify the LLM client still functions without tracing.

### Langfuse Integration (When Enabled)

- **CallbackHandler creation**: When tracing is enabled and credentials are available, a Langfuse `CallbackHandler` is created in the LLM client. Verify the handler is included in LangChain callbacks for every LLM call.

- **Environment variable management**: The LLM client sets `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST` as environment variables. Original values are backed up in `_original_env` and can be restored. Verify environment variables are set correctly.

- **Credential sources**: Langfuse keys can come from either `LLMConfig` fields or `settings` (environment). Config fields take precedence. Verify the fallback chain works.

- **Flush on cleanup**: `client.flush()` ensures all traces are sent to Langfuse before process exit. Verify flush is called and handles errors gracefully.

### Tracing Metadata

- **LLMMessageMetadata**: Carries `request_id`, `session_id`, `trace_id`, `span_id`, `user_id`, and optional `llm_metrics`. Defined in `llm_schemas.py`. Verify metadata can be passed through the tracing pipeline.

- **LLMMetrics**: Captures `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `latency_ms`, and `ttft_ms` (time to first token for streaming). Defined in `llm_schemas.py`. Verify all fields are populated from LangChain response metadata.

### Search Flow Tracing

- **Trace hierarchy**: Search requests produce a nested trace structure when Langfuse is enabled:
  ```
  search_request (top-level, with session_id metadata)
  └── search_agent_run (agent loop span)
      ├── tool_call (per tool invocation)
      │   ├── sql_execution (SQL tool)
      │   └── vector_search (vector tool)
      └── ...
  └── why_this_person_batch (explainer span)
      └── why_this_person (per-batch LLM call)
  ```
  When Langfuse is disabled, the `@observe` decorators from the guard are no-ops and the hierarchy is not recorded.

- **Per-tool spans**: 9 tool files and the search agent use `@observe` from `langfuse_guard`. When enabled, each tool call creates its own span. Consumer files: `career_tool.py`, `vector_tool.py`, `web_tool.py`, `network_tool.py`, `company_tool.py`, `sql_tool.py`, `result_set_tool.py`, `intro_tool.py`, `profile_tool.py`.

- **Controller-level tracing**: `search_controller.py` and `best_hop_controller.py` use `get_client` and `propagate_attributes` from the guard to create top-level traces and propagate context.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Tracing provider | Langfuse via LangChain callback | Direct Langfuse SDK or OpenTelemetry | LangChain callback integrates naturally with the existing LLM client |
| 2026-03-25 | Toggle granularity | Per-LLMConfig | Global environment variable | Allows different agents to have different tracing settings |
| 2026-03-25 | Credential management | Env var injection with backup | Dependency injection | Langfuse SDK expects env vars; backup/restore prevents side effects |
| 2026-04-01 | Search flow instrumentation | `@observe` decorators + guard module | Manual span creation via SDK | Decorator approach is less invasive, guard makes it zero-cost when disabled |
| 2026-04-08 | OSS default | Disabled by default (`LANGFUSE_ENABLED=false`) | Enabled by default | OSS users should not need Langfuse credentials to run the app; guard module provides zero-overhead no-ops |

## Not Included

- Trace sampling (all-or-nothing)
- Trace export to non-Langfuse backends (OpenTelemetry, Datadog)
- Dashboard or alerting integration
- Cost tracking in traces (cost_usd is always 0)
- Automatic Langfuse SDK installation (it is a dependency but only loaded when enabled)

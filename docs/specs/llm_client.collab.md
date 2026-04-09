---
feature: llm-client
module: backend/src/utilities/llm_manager
linked_files:
  - backend/src/utilities/llm_manager/llm_client.py
  - backend/src/utilities/llm_manager/llm_factory.py
  - backend/src/utilities/llm_manager/llm_schemas.py
  - backend/src/utilities/llm_manager/llm_message.py
  - backend/src/utilities/llm_manager/llm_client_user.py
  - backend/src/utilities/llm_manager/conversation_manager.py
  - backend/src/utilities/llm_manager/embedding_client.py
  - backend/src/utilities/llm_manager/embedding_provider.py
  - backend/src/utilities/llm_manager/embedding_factory.py
  - backend/src/utilities/llm_manager/openai_embedding_provider.py
  - backend/src/utilities/llm_manager/local_embedding_provider.py
  - backend/src/utilities/llm_manager/exceptions.py
version: 1
last_verified: "2026-04-09"
---

# LLM Client

**Created:** 2026-04-09 — Adapted from internal spec for LinkedOut OSS

## Intent

Provide a reusable LLM client abstraction with provider selection, structured output support, streaming, metrics capture, and mockability for tests. The implementation uses LangChain for LLM provider abstraction. Embedding support uses a dual-provider architecture (OpenAI API and local nomic-embed-text) with a factory that selects based on configuration.

## Behaviors

### LLMClient (Abstract)

- **Three call modes**: `call_llm(message)` returns plain text. `call_llm_structured(message, response_model)` returns a Pydantic model instance. `acall_llm_stream(message)` yields string chunks asynchronously. Verify each mode returns the expected type.

- **Tool-calling mode**: `call_llm_with_tools(message, tools)` binds tool definitions to the LLM and returns an `LLMToolResponse`. The tools parameter accepts a list of tool-definition dicts (OpenAI function-calling format). `LLMToolResponse` contains `content` (text output), `tool_calls` (list of `{id, name, args}` dicts), and a `has_tool_calls` property. Verify the method returns tool calls when the LLM selects a tool, and returns empty tool_calls with text content when it does not.

- **User context tracking**: The client accepts an `LLMClientUser` which provides `get_agent_id()`, `get_session_id()`, and `record_llm_cost()` for metrics callback. `record_llm_cost` is an optional hook with a default no-op implementation. Verify the user's `record_llm_cost` is called after each LLM call.

- **SystemUser for non-agent callers**: `SystemUser(agent_id)` is a lightweight `LLMClientUser` implementation for callers that don't extend `BaseAgent`. It returns the given agent_id from `get_agent_id()` and None from `get_session_id()`. Verify it satisfies the `LLMClientUser` interface.

### LangChainLLMClient

- **OpenAI provider**: When `provider=OPENAI`, a `ChatOpenAI` client is created with the configured model, temperature, max_tokens, retries, and timeout. Verify the client is functional with valid credentials.

- **Azure OpenAI provider**: When `provider=AZURE_OPENAI`, an `AzureChatOpenAI` client is created. Requires `api_base` and `api_version`. Verify `LLMConfigurationError` is raised if either is missing.

- **Structured output with raw**: `call_llm_structured` uses `with_structured_output(response_model, include_raw=True)` to get both parsed and raw responses. Metrics are extracted from the raw response. Verify the parsed response is returned as the result.

- **Latency tracking**: Every call measures latency via `time.perf_counter_ns()`. Verify `latency_ms` is included in the metrics callback.

- **Token usage extraction**: Token counts are extracted from `usage_metadata` or `response_metadata.token_usage`. Verify input_tokens, output_tokens, and total_tokens are captured.

- **Tool binding per call**: `call_llm_with_tools` calls `bind_tools(tools)` on the underlying LangChain model for each invocation. This avoids stale state across calls. Tool calls are extracted from the LangChain response's `tool_calls` attribute and normalized into `{id, name, args}` dicts. Verify metrics are recorded and Langfuse tracing captures tool-calling invocations.

- **Langfuse tracing**: A `CallbackHandler` from `langfuse.langchain` is attached to all LLM invocations when `enable_tracing=True` and Langfuse credentials are available. Credentials are resolved from LLMConfig fields or `shared.config`. A `flush()` method ensures traces are sent before process exit. Verify tracing is disabled gracefully when credentials are absent.

### LLMConfig

- **Provider enum**: Supports `OPENAI`, `AZURE_OPENAI`, `GROQ`, `GEMINI` (only OpenAI and Azure are implemented). Verify unsupported providers raise `LLMProviderError`.

- **Config-driven retries**: `max_retries` (default 2) and `timeout` (default 120s) are passed to the LangChain client. Verify the values are applied.

- **SecretStr for API key**: `api_key` uses Pydantic `SecretStr` to prevent accidental logging. Verify the key is not exposed in repr or JSON serialization.

- **Langfuse configuration fields**: `langfuse_public_key`, `langfuse_secret_key` (SecretStr), `langfuse_host`, and `enable_tracing` (default True) control observability.

### LLMMessage

- **Message builder**: Supports `add_system_message`, `add_user_message`, `add_assistant_message` (with optional tool_calls), and `add_tool_message` (with tool_call_id). `from_prompt(prompt, variables)` creates a message from a PromptSchema with template variable substitution. Verify messages are converted to LangChain format via `to_langchain_messages()`.

- **Combine method**: `combine(other)` creates a new LLMMessage containing all messages from both instances. Verify deep copy semantics.

### LLMFactory

- **Factory creation**: `LLMFactory.create_client(user, config)` creates the appropriate LLMClient subclass. Currently returns a `LangChainLLMClient` for all supported providers. Verify it returns a `LangChainLLMClient`.

### Supporting Schemas

- **LLMMetrics**: Captures request_id, prompt_tokens, completion_tokens, total_tokens, cost_usd, latency_ms, and ttft_ms (streaming only).

- **LLMMessageMetadata**: Contains request_id, session_id, trace_id, span_id, user_id, and optional llm_metrics for distributed tracing correlation.

- **LLMToolResponse**: Contains content (str), tool_calls (list of dicts), and `has_tool_calls` property.

## Embedding Layer

### EmbeddingProvider (Abstract)

An ABC defining the interface all embedding backends implement. Six required methods:

- `embed(texts) -> list[list[float]]` — batch embedding.
- `embed_single(text) -> list[float]` — single text embedding.
- `dimension() -> int` — vector dimension for this provider/model.
- `model_name() -> str` — human-readable model identifier.
- `estimate_time(count) -> str` — human-readable time estimate.
- `estimate_cost(count) -> str | None` — human-readable cost estimate, or None if free.

### build_embedding_text (shared utility)

`build_embedding_text(profile: dict) -> str` constructs embedding input from a profile dict. Format: `{full_name} | {headline} | {about} | Experience: {company} - {title}, ...`. Lives in `embedding_provider.py` and is used by all providers.

### OpenAIEmbeddingProvider

Wraps `EmbeddingClient` to conform to the `EmbeddingProvider` ABC. Uses OpenAI's text-embedding API.

- **Config-driven**: Reads model and dimensions from `shared.config` embedding settings. Default model: `text-embedding-3-small`, default dimensions: 1536.
- **API key required**: Raises `RuntimeError` if `OPENAI_API_KEY` is not configured (checked at init).
- **Batch API support** (provider-specific extras): `embed_batch_async(items, output_path)` creates a JSONL file, submits to OpenAI Batch API, and polls until completion. `cancel_batch(batch_id)` cancels and retrieves partial results.
- **Cost estimation**: ~$0.02 per 1M tokens, ~500 tokens per profile.
- **Time estimation**: ~100 texts per minute via real-time API.

### LocalEmbeddingProvider

Uses `nomic-ai/nomic-embed-text-v1.5` via sentence-transformers with ONNX quantized backend for CPU inference.

- **Lazy model loading**: Model is not loaded at init time. Downloaded (~275MB) and loaded on first `embed()` call. Cached in `{data_dir}/models/`.
- **Dimensions**: 768 (fixed for nomic-embed-text-v1.5).
- **Free**: `estimate_cost()` returns None.
- **Time estimation**: ~7 profiles/second on modern CPU.
- **Dependency requirement**: Requires `sentence-transformers` and `onnxruntime`. Raises `ImportError` with install instructions if missing.

### EmbeddingClient (Legacy/Internal)

Direct OpenAI API wrapper used internally by `OpenAIEmbeddingProvider`. Provides `embed_text`, `embed_batch`, `create_batch_file`, `submit_batch`, `poll_batch`, `cancel_and_get_results`. Empty texts in batch calls get zero vectors.

### Embedding Factory

- `get_embedding_provider(provider, model)` returns an `EmbeddingProvider` instance. Provider defaults to `LINKEDOUT_EMBEDDING_PROVIDER` from config. Supports `'openai'` and `'local'`. Raises `ValueError` for unknown providers.
- `get_embedding_column_name(provider)` maps provider model name to the correct `crawled_profile` column: models containing `'nomic'` map to `embedding_nomic`, everything else to `embedding_openai`.

## ConversationManager (Companion Utility)

A separate class in `conversation_manager.py`. LLMClient itself is unchanged — ConversationManager is a standalone utility that uses an LLMClient instance for summarization.

### ConversationManager

- **Constructor**: `ConversationManager(llm_client, summarization_prompt, recent_turns=4)`. The `llm_client` is used only for generating summaries of older turns. The `summarization_prompt` is caller-provided (domain-specific). `recent_turns` defaults to 4.

- **build_history**: `build_history(turns: list[dict]) -> SummaryResult`. Accepts turn rows from DB ordered by `turn_number`. Each dict must have `user_query` (str). Optional keys: `transcript` (list of message dicts), `summary` (str or None). Returns a `SummaryResult`.

- **Recent turns verbatim**: The most recent N turns (per `recent_turns`) are converted to user/assistant message pairs. For each turn, the user_query becomes a user message; the last assistant message from the transcript becomes an assistant message.

- **Older turns summarized**: Turns beyond the recent window are collapsed into a single `[Previous conversation summary]` assistant message. If a turn already has a cached `summary`, it is reused. Uncached turns are batch-summarized via a single `call_llm` invocation using the caller's summarization prompt.

- **Graceful fallback**: If summary generation fails (LLM error), falls back to concatenating raw `user_query` strings as the summary.

### SummaryResult

- **messages**: `list[dict]` — ready to inject into LLMMessage. Contains the summary message (if any) followed by recent turn messages.

- **generated_summaries**: `dict[int, str]` — maps turn index (in the input list) to newly generated summary text. Caller is responsible for persisting these back to DB so they are cached on subsequent calls.

## Exceptions

- `LLMError` — base exception for all LLM errors.
- `LLMConfigurationError(LLMError)` — missing or invalid configuration.
- `LLMProviderError(LLMError)` — provider API failures.
- `LLMParsingError(LLMError)` — structured output parse failures.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Provider abstraction | LangChain | Direct API calls | LangChain handles retries, structured output, and provider switching |
| 2026-03-25 | Metrics pattern | Callback via LLMClientUser interface | Return value or global collector | Allows per-agent metrics capture without shared state |
| 2026-03-25 | Streaming | Async generator | Sync streaming | Aligns with FastAPI's async support |
| 2026-03-26 | Embedding client | Direct OpenAI SDK | LangChain `OpenAIEmbeddings` | EmbeddingClient uses `openai.OpenAI` directly for batch API support, dimensions param, and simpler control |
| 2026-04-01 | Tool-calling abstraction | `call_llm_with_tools` in LLMClient | Tool-calling in each consumer via direct ChatOpenAI | Guarantees all LLM calls flow through the abstraction for Langfuse tracing; prevents LangChain type leakage via LLMToolResponse |
| 2026-04-02 | Conversation history | Separate ConversationManager class | Adding history methods to LLMClient | LLMClient stays single-purpose; ConversationManager is generic infrastructure that any agent can use with its own summarization prompt |
| 2026-04-09 | Dual embedding providers | EmbeddingProvider ABC + factory | Single OpenAI-only client | OSS users may not have OpenAI keys; local nomic option enables zero-cost embedding on CPU |

## Not Included

- Groq or Gemini provider implementations (enum values exist but not wired)
- Token cost calculation (cost_usd is always passed as 0)
- Response caching
- Prompt token counting before sending
- Multi-turn tool loop orchestration (loop logic stays in consumers like SearchAgent)

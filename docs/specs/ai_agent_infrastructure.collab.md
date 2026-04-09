---
feature: ai-agent-infrastructure
module: src/common/services, src/common/entities
linked_files:
  - src/common/services/base_agent.py
  - src/common/services/agent_executor_service.py
  - src/common/services/agent_run_service.py
  - src/common/services/base_context.py
  - src/common/services/post_llm_pipeline.py
  - src/common/entities/agent_run_entity.py
  - src/common/repositories/agent_run_repository.py
  - src/common/controllers/agent_run_controller.py
  - src/project_mgmt/agents/task_triage/task_triage_agent.py
last_verified: 2026-03-25
version: 2
---

# AI Agent Infrastructure

**Created:** 2026-03-25 — Backfilled from existing implementation
**Updated:** 2026-03-25 — Added AgentRun Controller (CRUDRouterFactory) behaviors

## Intent

Provide a reusable AI agent stack with lifecycle management, context building, LLM invocation, post-validation, and persistence. Agents are registered in a module-level registry and executed via an executor that tracks the full lifecycle from PENDING through RUNNING to COMPLETED or FAILED.

## Behaviors

### BaseAgent

- **LLM client creation**: BaseAgent provides `_create_llm_client()` which builds an LLMClient from backend_config settings (provider, model, API key). Verify the client is configured with the correct provider and model.

- **Prompt loading**: `_load_prompt(prompt_name)` retrieves a prompt via PromptFactory. Verify the prompt is loaded from the configured store (local file or Langfuse).

- **Full LLM call flow**: `_call_llm(prompt_name, variables, response_model)` loads the prompt, builds an LLMMessage, calls `call_llm_structured`, and captures `_llm_input` for metrics. Verify the returned object is an instance of `response_model`.

- **Metrics capture**: After an LLM call, `record_llm_cost` combines agent-side input with client-side output metadata (latency, tokens, cost). `get_llm_metrics()` returns the captured metrics. Verify metrics include llm_input, llm_output, llm_cost_usd, and llm_latency_ms.

- **Abstract run method**: Subclasses must implement `run(**kwargs)`. Verify that instantiating BaseAgent directly raises TypeError.

### AgentRunEntity

- **Lifecycle tracking**: AgentRunEntity stores `status` (PENDING, RUNNING, COMPLETED, FAILED), `started_at`, `completed_at`, `error_message`. Verify status transitions are recorded with timestamps.

- **LLM tracking fields**: Stores `llm_input`, `llm_output` (JSON), `llm_cost_usd` (float), `llm_latency_ms` (integer), `llm_metadata` (JSON). Verify all fields are persisted after a completed run.

- **Timestamped ID**: Uses `Nanoid.make_timestamped_id('arn')` for sortable, unique IDs. Verify IDs start with 'arn' prefix.

- **Tenant-BU scoped**: Extends TenantBuMixin. Verify agent runs are isolated per tenant and BU.

### Agent Executor Service

- **Agent registry**: `register_agent(agent_type, agent_class)` adds an agent to the module-level registry. `get_registered_agent(agent_type)` retrieves it. Verify registered agents can be looked up by type string.

- **Execute with lifecycle**: `execute_agent()` creates (or reuses) an AgentRun record, sets RUNNING, executes the agent, captures LLM metrics, and sets COMPLETED. On error, sets FAILED with error message. Verify the full lifecycle is tracked.

- **Pre-created record mode**: When `agent_run_id` is provided, the executor skips creation and reuses the existing record. Verify the existing record transitions through RUNNING to COMPLETED.

- **Error resilience**: If the agent fails, the executor updates status to FAILED. If the status update itself fails, the error is logged but does not mask the original exception. Verify the original exception is re-raised.

### BaseAgentContext

- **Frozen immutable context**: `BaseAgentContext` is a Pydantic model with `frozen=True`. It carries `tenant_id` and `bu_id`. Subclasses add agent-specific fields. Verify mutation raises a validation error.

### Post-LLM Pipeline

- **Validator chain**: `validate_llm_output(output, validators)` runs a list of validator functions. Each returns a list of error strings. Verify errors from all validators are aggregated.

- **PostValidationError**: When validation errors exist, raising `PostValidationError(errors)` carries the error list. Verify the exception message includes the error count.

- **Validator exception handling**: If a validator function itself raises, the exception is caught and added as an error string. Verify the pipeline does not crash on a broken validator.

### AgentRun Controller (CRUDRouterFactory)

- **Standard CRUD via factory**: AgentRun controller uses `CRUDRouterConfig + create_crud_router()` for all six standard endpoints (list, create, bulk create, get, update, delete) at `/tenants/{tid}/bus/{bid}/agent-runs`. Verify all endpoints are accessible.

- **Custom invoke endpoint**: A `POST /invoke` endpoint creates an AgentRun record synchronously (PENDING), then schedules agent execution as a background task. Returns 202 Accepted with agent_run_id. Verify the endpoint returns immediately with a pollable ID.

- **JSONB storage columns**: Five columns (`llm_input`, `llm_output`, `llm_metadata`, `input_params`, `output_data`) use PostgreSQL JSONB type. Verify JSON data is stored and retrieved correctly.

### Example: TaskTriageAgent

- **Context building**: Uses `TaskTriageContextBuilder` to load task, project, labels, and sibling tasks. Verify the context is populated from DB data.

- **LLM call with structured output**: Calls `_call_llm` with `TaskTriageResponse` model. Verify the response includes suggested_priority, estimated_hours, suggested_labels, analysis, and confidence_score.

- **Post-validation**: Validates priority range (1-5) and positive estimated_hours. Verify `PostValidationError` is raised for out-of-range values.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | Agent registration | Module-level dict registry | Class decorator or DI container | Simple, explicit, easy to debug |
| 2026-03-25 | Context pattern | Frozen Pydantic BaseModel | Mutable dict or dataclass | Immutability prevents accidental mutation; Pydantic provides validation |
| 2026-03-25 | Lifecycle sessions | Separate sessions for create, execute, update | Single session | Prevents long-running transactions and session leaks during LLM calls |

## Not Included

- Async agent execution (background tasks / Celery)
- Agent retry on LLM failure (retry is at the LLM client level)
- Agent chaining or orchestration (agents are independent units)
- Cost calculation (llm_cost_usd is always 0 currently)

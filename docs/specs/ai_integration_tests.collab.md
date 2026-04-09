---
feature: ai-integration-tests
module: tests/common, tests/integration
linked_files:
  - tests/common/repositories/test_agent_run_repository.py
  - tests/common/controllers/test_agent_run_controller.py
  - tests/common/services/test_agent_run_service.py
  - tests/integration/test_agent_run_integration.py
  - src/project_mgmt/agents/task_triage/
last_verified: 2026-03-25
version: 1
---

# AI Integration Tests

**Created:** 2026-03-25 — Backfilled from existing implementation

## Intent

Provide tests for the AI agent infrastructure that verify lifecycle management, context building, post-validation, and persistence — all without requiring live LLM calls. Agent tests mock the LLM client to test the orchestration logic around it.

## Behaviors

### AgentRun MVCS Tests

- **Repository tests**: AgentRun repository tests verify CRUD operations against SQLite. Create an agent run, query by ID, list with filters, update status. Verify all standard repository operations work for the agent_run table.

- **Service tests**: AgentRun service tests mock the repository. Verify create_agent_run, update_status, and get_by_id work correctly with schema conversion.

- **Controller tests**: AgentRun controller tests mock the service. Verify HTTP endpoints return correct status codes and response schemas for agent run management.

### Agent Lifecycle Tests

- **Full lifecycle (integration)**: An integration test creates an agent run record, transitions through PENDING -> RUNNING -> COMPLETED, and verifies all timestamps and metadata are persisted. Verify the completed record has `started_at`, `completed_at`, and status=COMPLETED.

- **Failure lifecycle**: An agent run that fails transitions to FAILED with an error_message. Verify the error is persisted and the completed_at timestamp is set.

- **LLM metrics persistence**: After a successful agent run, LLM metrics (llm_input, llm_output, llm_cost_usd, llm_latency_ms, llm_metadata) are stored on the agent run record. Verify all metrics fields are non-null after completion.

### Agent Execution Tests

- **Mocked LLM call**: Agent tests mock `BaseAgent._call_llm` to return a predetermined response. Verify the agent processes the mocked response through post-validation and enrichment.

- **Post-validation testing**: Tests provide LLM responses that violate validation rules (e.g., out-of-range priority). Verify `PostValidationError` is raised with the expected error list.

- **Context builder testing**: Tests verify that the context builder loads the correct entities from the database and assembles them into a frozen context object. Verify the context has all required fields populated.

### Live LLM Tests

- **Marker-based isolation**: Live LLM tests use `@pytest.mark.live_llm` and are only run in the precommit suite. Verify they are excluded from regular unit test runs.

- **Real LLM verification**: At least one test makes a real LLM call to verify the full pipeline (prompt loading, LLM invocation, structured output parsing). Verify the response parses into the expected Pydantic model.

## Decisions

| Date | Decision | Chose | Over | Because |
|------|----------|-------|------|---------|
| 2026-03-25 | LLM mocking | Mock at _call_llm level | Mock at HTTP level or provider level | Testing agent logic, not LLM client plumbing |
| 2026-03-25 | Live LLM tests | Separate marker, run in precommit only | Always skip or always run | Verifies the real pipeline works without slowing unit tests |
| 2026-03-25 | Agent run testing | Full MVCS test suite for AgentRun entity | Only lifecycle tests | AgentRun is a first-class entity deserving the same test coverage |

## Not Included

- Evaluation framework (scoring LLM output quality)
- Benchmark tests for LLM latency
- Concurrent agent execution tests
- Mock Langfuse trace verification

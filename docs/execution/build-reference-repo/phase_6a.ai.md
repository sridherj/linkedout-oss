# Phase 6a: AI Agent Infrastructure (LLM, BaseAgent, AgentRun MVCS)

## Execution Context
**Depends on**: Phase 3 (domain entities exist)
**Blocks**: Phase 5b (agent test patterns), Phase 6b (TaskTriageAgent)
**Parallel with**: Phase 4 (auth), Phase 5a (basic test infra)

## Goal
Build reusable agent infrastructure: AgentRun MVCS in `src/common/`, BaseAgent generalization, agent executor with registry pattern, context builder pattern, post-LLM pipeline helpers. No example agent yet (Phase 6b).

## Critical Reconciliation Decisions (Baked In)
- **I4**: Module name `project_mgmt` everywhere (agent registration uses `project_mgmt.agents`, NOT `project_management.agents`)
- **I7**: Single agent registry in `agent_executor_service.py`. Phase 7 CLI uses this registry (does NOT create its own).
- **I8**: AgentRun ID prefix is `arn` (NOT `ar`). AgentRunStatus uses uppercase (PENDING, RUNNING, COMPLETED, FAILED).

## Pre-Conditions
- Phase 3 DONE: Project/Task entities exist (needed for context builder example)
- LLM client + prompt manager already generic in `src/utilities/` (no changes needed)
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- AgentRunEntity has full MVCS stack in `src/common/`
- BaseAgent generalized from BasePlannerAgent (no rcm references)
- Agent executor with registry pattern works
- `LLM_TRACING_ENABLED` config toggle added
- Agent run lifecycle: PENDING -> RUNNING -> COMPLETED/FAILED
- LLM client and prompt manager unchanged (already generic)

---

## Step 1: Add `LLM_TRACING_ENABLED` Config

### File: `src/shared/config/config.py`

Add:
```python
LLM_TRACING_ENABLED: bool = os.getenv('LLM_TRACING_ENABLED', 'false').lower() == 'true'
```

This is independent of `PROMPT_FROM_LOCAL_FILE`. Tracing can be on/off regardless of prompt source.

**Verify**: Config loads without error.

---

## Step 2: AgentRun MVCS Stack

### 2a: Entity — `src/common/entities/agent_run_entity.py`

Source: `src/rcm/planner/entities/agent_run_entity.py`

**Changes**: Remove ALL rcm relationships (lot_allocations, schedules, etc.). Add generic `output` field (JSON).

```python
class AgentRunEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'agent_run'
    id_prefix = 'arn'

    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='PENDING')
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    llm_input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    llm_output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    llm_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

### 2b: Schemas — `src/common/schemas/agent_run_schema.py`

- `AgentRunStatus(StrEnum)`: PENDING, RUNNING, COMPLETED, FAILED
- `AgentRunSchema(BaseModel)` with `model_config = ConfigDict(from_attributes=True)`
- `AgentRunSortByFields(StrEnum)`: CREATED_AT, STARTED_AT, STATUS, AGENT_TYPE
- Standard request/response schemas using base mixins
- `InvokeAgentRequestSchema`: agent_type, input_params
- `InvokeAgentResponseSchema`: agent_run_id, status, message

### 2c: Repository — `src/common/repositories/agent_run_repository.py`

```python
class AgentRunRepository(BaseRepository[AgentRunEntity, AgentRunSortByFields]):
    _entity_class = AgentRunEntity
    _default_sort_field = 'created_at'
    _entity_name = 'agent_run'
    def _get_filter_specs(self): return [
        FilterSpec('agent_type', 'eq'),
        FilterSpec('status', 'eq'),
    ]
```

### 2d: Service — `src/common/services/agent_run_service.py`

Standard BaseService subclass plus convenience methods:
- `create_agent_run(tenant_id, bu_id, agent_type, input_params) -> AgentRunSchema`
- `update_status(tenant_id, bu_id, agent_run_id, status, error_message=None, output=None, started_at=None, completed_at=None, llm_cost_usd=None, llm_latency_ms=None, llm_metadata=None) -> Optional[AgentRunSchema]`

### 2e: Controller — `src/common/controllers/agent_run_controller.py`

```python
router = APIRouter(prefix="/tenants/{tenant_id}/bus/{bu_id}/agent-runs", tags=["Agent Runs"])

POST /            -> invoke_agent (202, creates run + background execution)
GET /             -> list_agent_runs (pagination, filters)
GET /{agent_run_id} -> get_agent_run
```

POST returns 202 (accepted) and kicks off background task via `BackgroundTasks`.

---

## Step 3: Generalize BaseAgent

### File: `src/common/services/base_agent.py`

Source: `src/rcm/planner/services/base_planner_agent.py`

Rename `BasePlannerAgent` -> `BaseAgent`. Keep all generic functionality:

```python
class BaseAgent(LLMClientUser, ABC):
    """Base class for all AI agents."""

    def __init__(self, session: Session):
        self._session = session
        self._agent_id = self.__class__.__name__
        self._llm_metrics = {}

    # LLMClientUser interface
    def get_agent_id(self) -> str: ...
    def record_llm_cost(self, cost_usd, metadata) -> None: ...
    def get_llm_metrics(self) -> Dict: ...

    # LLM helpers
    def _create_llm_client(self) -> LLMClient: ...
    def _load_prompt(self, prompt_name) -> PromptSchema: ...
    def _call_llm(self, prompt_name, variables, response_model) -> BaseModel: ...

    # Abstract interface
    @abstractmethod
    def run(self, **kwargs) -> Optional[str]: ...
```

Key: BaseAgent does NOT manage lifecycle (PENDING -> RUNNING -> COMPLETED). The executor service does that.

Wire `LLM_TRACING_ENABLED` into `_create_llm_client()`:
```python
enable_tracing=config.LLM_TRACING_ENABLED,
langfuse_public_key=config.LANGFUSE_PUBLIC_KEY if config.LLM_TRACING_ENABLED else None,
```

---

## Step 4: Agent Executor with Registry

### File: `src/common/services/agent_executor_service.py`

```python
_agent_registry: Dict[str, Type[BaseAgent]] = {}

def register_agent(agent_type: str, agent_class: Type[BaseAgent]) -> None:
    _agent_registry[agent_type] = agent_class

def get_registered_agent(agent_type: str) -> Type[BaseAgent]:
    if agent_type not in _agent_registry:
        raise ValueError(f"Unknown agent type: {agent_type}. Registered: {list(_agent_registry.keys())}")
    return _agent_registry[agent_type]

def execute_agent(tenant_id, bu_id, agent_type, input_params, agent_run_id) -> str:
    """Execute with lifecycle: mark RUNNING, run agent, mark COMPLETED/FAILED."""
    # 1. Mark RUNNING
    # 2. Instantiate agent from registry, call agent.run()
    # 3. Capture LLM metrics
    # 4. Mark COMPLETED or FAILED (with error_message)
    # Uses fresh DB sessions (not request session)
```

Domain modules register agents in their `__init__.py`:
```python
# src/project_mgmt/agents/__init__.py
from common.services.agent_executor_service import register_agent
from project_mgmt.agents.task_triage.task_triage_agent import TaskTriageAgent
register_agent('task_triage', TaskTriageAgent)
```

---

## Step 5: Context Builder Pattern

### File: `src/common/services/base_context.py`

Lightweight base — pattern documentation, not a framework:
```python
class BaseAgentContext(BaseModel):
    """Immutable context snapshot. Built once, consumed by agent."""
    model_config = ConfigDict(frozen=True)
    tenant_id: str
    bu_id: str
```

No abstract builder class. Builders are simple functions/classes per agent.

---

## Step 6: Post-LLM Pipeline Helpers

### File: `src/common/services/post_llm_pipeline.py`

```python
class PostValidationError(Exception):
    def __init__(self, message, validation_errors=None): ...

def validate_llm_output(output: BaseModel, validators: list[callable]) -> list[str]:
    """Run validators. Each returns None (pass) or error string (fail)."""
```

Not a framework — agents call validate -> enrich -> persist in their `run()`.

---

## Step 7: Wire into main.py

```python
from common.controllers.agent_run_controller import router as agent_run_router
app.include_router(agent_run_router)
```

Add AgentRunEntity import to `conftest.py` and `migrations/env.py`.

Do NOT add CLI commands (Phase 7 does CLI restructure).

---

## Files Summary

### Create (~10 files)
| File | Description |
|------|-------------|
| `src/common/entities/agent_run_entity.py` | AgentRunEntity |
| `src/common/schemas/agent_run_schema.py` | All CRUD schemas |
| `src/common/repositories/agent_run_repository.py` | Repository |
| `src/common/services/agent_run_service.py` | Service + lifecycle methods |
| `src/common/controllers/agent_run_controller.py` | REST endpoints |
| `src/common/services/base_agent.py` | BaseAgent (from BasePlannerAgent) |
| `src/common/services/agent_executor_service.py` | Registry + executor |
| `src/common/services/base_context.py` | BaseAgentContext |
| `src/common/services/post_llm_pipeline.py` | Post-validation helpers |

### Modify (~4 files)
| File | Change |
|------|--------|
| `src/shared/config/config.py` | Add LLM_TRACING_ENABLED |
| `main.py` | Add agent_run_router |
| `conftest.py` | Add AgentRunEntity import |
| `migrations/env.py` | Add AgentRunEntity import |
| `src/common/entities/__init__.py` | Export AgentRunEntity |

### Unchanged (Already Generic)
- `src/utilities/llm_manager/*` — no changes needed
- `src/utilities/prompt_manager/*` — no changes needed

## Risks
1. **Import cycle**: `agent_executor_service` imports from `agent_run_service` and agent classes import from services. Deferred imports in registration prevent cycles.
2. **BackgroundTasks and DB sessions**: execute_agent must create fresh sessions (not reuse request session). Use `db_session_manager.get_session()` directly.

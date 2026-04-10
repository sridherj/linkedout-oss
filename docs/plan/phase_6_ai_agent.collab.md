# Phase 6: AI Agent Infrastructure — Detailed Execution Plan

## Goal
Build a reusable AI agent stack with lifecycle management, LLM client, prompt management, tracing, context builder pattern, post-LLM pipeline, and a working example agent (`TaskTriageAgent`). All generalized from the existing linkedout/rcm planner code.

## Pre-Conditions
- Phase 3 DONE: Project/Task/Label/Priority entities exist with full MVCS stacks
- Phase 5 DONE: Test infrastructure in place (all 4 layers, seeding, parallel execution)
- Existing linkedout code in `src/utilities/llm_manager/`, `src/utilities/prompt_manager/`, `src/rcm/planner/` serves as living reference

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- `AgentRunEntity` has full MVCS stack in `src/common/` (not rcm-specific)
- `BasePlannerAgent` generalized to `BaseAgent` in `src/common/`
- LLM client and prompt manager generalized (no rcm references)
- `TaskTriageAgent` demonstrates full pipeline: context build → prompt → LLM → validate → enrich → persist
- Agent tests pass without live LLM calls
- Prompt source switchable via `PROMPT_FROM_LOCAL_FILE`
- Tracing on/off via `LLM_TRACING_ENABLED` (independent of prompt source)

---

## Key Findings from Code Review

### What's Already Generic (No Changes Needed)
| File | Status |
|------|--------|
| `src/utilities/llm_manager/llm_client.py` | `LLMClient` ABC + `LangChainLLMClient` — provider-agnostic, no domain refs |
| `src/utilities/llm_manager/llm_factory.py` | `LLMFactory.create_client()` — clean factory, no domain refs |
| `src/utilities/llm_manager/llm_message.py` | `LLMMessage` fluent builder — generic, no domain refs |
| `src/utilities/llm_manager/llm_schemas.py` | `LLMConfig`, `LLMMetrics`, `LLMMessageMetadata` — clean Pydantic models |
| `src/utilities/llm_manager/llm_client_user.py` | `LLMClientUser` ABC — generic interface |
| `src/utilities/llm_manager/exceptions.py` | Clean exception hierarchy |
| `src/utilities/prompt_manager/prompt_manager.py` | `PromptManager` + `PromptFactory` — generic |
| `src/utilities/prompt_manager/prompt_store.py` | `PromptStore` protocol — generic |
| `src/utilities/prompt_manager/local_file_store.py` | `LocalFilePromptStore` — generic |
| `src/utilities/prompt_manager/langfuse_store.py` | `LangfusePromptStore` — generic |
| `src/utilities/prompt_manager/prompt_schemas.py` | `PromptSchema`, `PromptMetadata`, `PromptType` — generic |
| `src/utilities/prompt_manager/prompt_config.py` | `PromptManagerConfig` — generic |
| `src/utilities/prompt_manager/cli.py` | Prompt CLI — generic |
| `src/shared/config/config.py` | Config with LLM/prompt settings — needs minor additions only |

### What Needs Changes (Generalize from Packhouse)
| Source File | Target | Issue |
|------------|--------|-------|
| `src/rcm/planner/entities/agent_run_entity.py` | `src/common/entities/agent_run_entity.py` | Has rcm-specific relationships (lot_allocations, schedules, etc.) |
| `src/rcm/planner/repositories/agent_run_repository.py` | `src/common/repositories/agent_run_repository.py` | Clean but in wrong module |
| `src/rcm/planner/services/agent_run_service.py` | `src/common/services/agent_run_service.py` | Has rcm-specific `AgentType` enum references |
| `src/rcm/planner/controllers/agent_run_controller.py` | `src/common/controllers/agent_run_controller.py` | Coupled to `agent_executor_service` (rcm pipeline) |
| `src/rcm/planner/services/base_planner_agent.py` | `src/common/services/base_agent.py` | Core pattern is generic; name and imports need generalization |
| `src/rcm/planner/services/agent_executor_service.py` | `src/common/services/agent_executor_service.py` | Heavily coupled to rcm agent types — needs complete redesign |

### Important Observations
1. **LLM client + prompt manager are already generic** — they live in `src/utilities/` and have zero rcm references. Only need to move/keep them and ensure config wiring.
2. **`BasePlannerAgent` is 90% generic** — it implements `LLMClientUser`, manages LLM client creation, prompt loading, and cost tracking. Only the name "Planner" and some imports are domain-specific.
3. **`AgentRunEntity` has the right fields** — agent_type, status, input_params, timestamps, LLM metrics. But its relationships to rcm entities (lot_allocations, schedules, etc.) must be removed in the generic version.
4. **`agent_executor_service` is the most domain-coupled** — it hardcodes a mapping from AgentType enum to specific agent classes. The generic version needs a registry pattern.
5. **Context builder pattern is excellent** — `LotPlannerContext` uses frozen Pydantic models with pre-computed lookups. This is the pattern to generalize.
6. **`LLM_TRACING_ENABLED` does not exist yet** — currently `enable_tracing` on `LLMConfig` is always True. Need to add independent toggle.
7. **AgentRun ID format** is `arn_YYYY-MM-DD-HH-MM-SS_<nanoid>` — good, keep this.
8. **Config already has** `PROMPT_FROM_LOCAL_FILE` and Langfuse keys — just need `LLM_TRACING_ENABLED`.

---

## Step 1: Add `LLM_TRACING_ENABLED` Config Toggle

### File: `src/shared/config/config.py`

**Current state**: `enable_tracing` on `LLMConfig` defaults to `True`. No independent toggle for tracing vs prompt source.

**Changes**:
1. Add `LLM_TRACING_ENABLED: bool` config variable (default: `False`)
2. Wire it into `LLMConfig.enable_tracing` in the config builder

**After**:
```python
# In config.py
LLM_TRACING_ENABLED: bool = os.getenv('LLM_TRACING_ENABLED', 'false').lower() == 'true'
```

**Verification**: Config loads without error. `LLM_TRACING_ENABLED=false` means no Langfuse traces even if Langfuse keys are set.

---

## Step 2: Generalize `AgentRunEntity` — Full MVCS Stack

### Step 2a: Entity — `src/common/entities/agent_run_entity.py`

**Source**: `src/rcm/planner/entities/agent_run_entity.py`

**Changes**:
1. Copy entity to `src/common/entities/`
2. Remove all rcm-specific relationships (`lot_allocations`, `inventory_assessments`, `line_layout_plans`, `schedules`, `resource_availability_assessments`, `machine_downtime_forecasts`, `worker_availability_forecasts`)
3. Keep all core fields
4. Add `output` field (JSONB, nullable) — generic result storage for any agent type

**After** — `src/common/entities/agent_run_entity.py`:
```python
class AgentRunEntity(TenantBuMixin, BaseEntity):
    __tablename__ = 'agent_run'
    id_prefix = 'arn'

    # Agent identification
    agent_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='PENDING')
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Input/Output
    input_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # LLM Metrics
    llm_input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    llm_output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    llm_cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

**ID generation**: Keep `arn_YYYY-MM-DD-HH-MM-SS_<nanoid>` format from `Nanoid.make_timestamped_id('arn')`.

### Step 2b: Schemas — `src/common/schemas/agent_run_schema.py`

**New file**. Define all CRUD schemas:

```python
class AgentRunStatus(StrEnum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'

class AgentRunSchema(BaseModel):
    """Response schema for AgentRun."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    bu_id: str
    agent_type: str
    status: str
    input_params: Optional[dict] = None
    output: Optional[dict] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    llm_cost_usd: Optional[float] = None
    llm_latency_ms: Optional[int] = None
    llm_metadata: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class AgentRunSortByFields(StrEnum):
    CREATED_AT = 'created_at'
    STARTED_AT = 'started_at'
    COMPLETED_AT = 'completed_at'
    STATUS = 'status'
    AGENT_TYPE = 'agent_type'

# List request
class ListAgentRunsRequestSchema(PaginateRequestSchema, TenantBuRequestMixin, SortableRequestMixin, ActiveFilterMixin):
    agent_type: Optional[str] = None
    status: Optional[str] = None
    sort_by: Optional[AgentRunSortByFields] = None

class ListAgentRunsResponseSchema(PaginateResponseSchema):
    agent_runs: List[AgentRunSchema]

# Create request (internal — agents create runs, not users directly)
class CreateAgentRunRequestSchema(BaseRequestSchema, TenantBuRequestMixin):
    agent_type: str
    input_params: Optional[dict] = None

class CreateAgentRunResponseSchema(BaseResponseSchema):
    agent_run: AgentRunSchema

# Get by ID
class GetAgentRunRequestSchema(BaseRequestSchema, TenantBuRequestMixin):
    agent_run_id: str

class GetAgentRunResponseSchema(BaseResponseSchema):
    agent_run: AgentRunSchema

# Invoke (public endpoint)
class InvokeAgentRequestSchema(BaseRequestSchema, TenantBuRequestMixin):
    agent_type: str
    input_params: Optional[dict] = None

class InvokeAgentResponseSchema(BaseResponseSchema):
    agent_run_id: str
    status: str
    message: str
```

### Step 2c: Repository — `src/common/repositories/agent_run_repository.py`

**Source**: `src/rcm/planner/repositories/agent_run_repository.py`

**Changes**: Copy, update imports to point to `src/common/entities/`.

```python
class AgentRunRepository(BaseRepository[AgentRunEntity, AgentRunSortByFields]):
    _entity_class = AgentRunEntity
    _default_sort_field = 'created_at'
    _entity_name = 'agent_run'

    def _get_filter_specs(self) -> List[FilterSpec]:
        return [
            FilterSpec(field_name='agent_type', filter_type='eq'),
            FilterSpec(field_name='status', filter_type='eq'),
        ]
```

### Step 2d: Service — `src/common/services/agent_run_service.py`

**Source**: `src/rcm/planner/services/agent_run_service.py`

**Changes**:
1. Copy, update imports
2. Keep `create_agent_run()` and `update_status()` convenience methods
3. Remove rcm-specific `AgentType` references — `agent_type` is just a string

```python
class AgentRunService(BaseService[AgentRunEntity, AgentRunSchema, AgentRunRepository]):
    _repository_class = AgentRunRepository
    _schema_class = AgentRunSchema
    _entity_class = AgentRunEntity
    _entity_name = 'agent_run'
    _entity_id_field = 'agent_run_id'

    def _extract_filter_kwargs(self, list_request) -> dict:
        return {
            'agent_type': getattr(list_request, 'agent_type', None),
            'status': getattr(list_request, 'status', None),
        }

    def _create_entity_from_request(self, create_request) -> AgentRunEntity:
        return AgentRunEntity(
            tenant_id=create_request.tenant_id,
            bu_id=create_request.bu_id,
            agent_type=create_request.agent_type,
            status=AgentRunStatus.PENDING,
            input_params=create_request.input_params,
        )

    def _update_entity_from_request(self, entity, update_request) -> None:
        # AgentRun updates go through update_status(), not generic update
        pass

    def create_agent_run(self, tenant_id: str, bu_id: str, agent_type: str, input_params: Optional[dict] = None) -> AgentRunSchema:
        """Convenience method to create a new agent run record."""
        entity = AgentRunEntity(
            tenant_id=tenant_id,
            bu_id=bu_id,
            agent_type=agent_type,
            status=AgentRunStatus.PENDING,
            input_params=input_params,
        )
        created = self._repository.create(entity)
        self.commit()
        return AgentRunSchema.model_validate(created)

    def update_status(
        self,
        tenant_id: str,
        bu_id: str,
        agent_run_id: str,
        status: str,
        error_message: Optional[str] = None,
        output: Optional[dict] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        llm_cost_usd: Optional[float] = None,
        llm_latency_ms: Optional[int] = None,
        llm_metadata: Optional[dict] = None,
    ) -> Optional[AgentRunSchema]:
        """Update agent run lifecycle state and metrics."""
        entity = self._repository.get_by_id(tenant_id, bu_id, agent_run_id)
        if not entity:
            return None
        entity.status = status
        if error_message is not None:
            entity.error_message = error_message
        if output is not None:
            entity.output = output
        if started_at is not None:
            entity.started_at = started_at
        if completed_at is not None:
            entity.completed_at = completed_at
        if llm_cost_usd is not None:
            entity.llm_cost_usd = llm_cost_usd
        if llm_latency_ms is not None:
            entity.llm_latency_ms = llm_latency_ms
        if llm_metadata is not None:
            entity.llm_metadata = llm_metadata
        updated = self._repository.update(entity)
        self.commit()
        return AgentRunSchema.model_validate(updated)
```

### Step 2e: Controller — `src/common/controllers/agent_run_controller.py`

**Changes from rcm version**:
1. Generic agent invocation endpoint (uses agent registry, not hardcoded types)
2. List and get-by-id endpoints
3. Background task execution

```python
router = APIRouter(prefix="/tenants/{tenant_id}/bus/{bu_id}/agent-runs", tags=["Agent Runs"])

@router.post("/", status_code=202, response_model=InvokeAgentResponseSchema)
async def invoke_agent(
    tenant_id: str,
    bu_id: str,
    request: InvokeAgentRequestSchema,
    background_tasks: BackgroundTasks,
    service: AgentRunService = Depends(create_service_dependency(AgentRunService, DbSessionType.WRITE)),
):
    """Create an agent run and execute it in the background."""
    agent_run = service.create_agent_run(tenant_id, bu_id, request.agent_type, request.input_params)
    background_tasks.add_task(execute_agent, tenant_id, bu_id, request.agent_type, request.input_params, agent_run.id)
    return InvokeAgentResponseSchema(agent_run_id=agent_run.id, status='PENDING', message='Agent run created')

@router.get("/", response_model=ListAgentRunsResponseSchema)
async def list_agent_runs(
    tenant_id: str, bu_id: str,
    agent_type: Optional[str] = None, status: Optional[str] = None,
    limit: int = 20, offset: int = 0,
    sort_by: Optional[AgentRunSortByFields] = None,
    sort_order: Optional[SortOrder] = None,
    service: AgentRunService = Depends(create_service_dependency(AgentRunService, DbSessionType.READ)),
):
    # Standard list with filters + pagination
    ...

@router.get("/{agent_run_id}", response_model=GetAgentRunResponseSchema)
async def get_agent_run(
    tenant_id: str, bu_id: str, agent_run_id: str,
    service: AgentRunService = Depends(create_service_dependency(AgentRunService, DbSessionType.READ)),
):
    # Standard get by ID
    ...
```

**Verification**: All CRUD endpoints return correct responses. Agent invocation returns 202 with agent_run_id.

---

## Step 3: Generalize `BaseAgent` (from `BasePlannerAgent`)

### File: `src/common/services/base_agent.py`

**Source**: `src/rcm/planner/services/base_planner_agent.py`

**What's already generic in the source**:
- Implements `LLMClientUser` interface
- `_create_llm_client()` — builds LLMClient from config
- `_load_prompt(prompt_name)` — loads prompt via PromptFactory
- `_call_llm(prompt_name, variables, response_model)` — structured LLM call
- `record_llm_cost()` — captures metrics
- `get_llm_metrics()` — returns captured metrics

**Changes**:
1. Rename `BasePlannerAgent` → `BaseAgent`
2. Add abstract `run()` method signature
3. Add lifecycle hooks: `_on_start()`, `_on_complete()`, `_on_fail()`
4. Add agent run tracking integration

```python
class BaseAgent(LLMClientUser, ABC):
    """
    Base class for all AI agents.

    Provides:
    - LLM client creation and prompt loading
    - Structured LLM calls with response model parsing
    - LLM cost/metrics tracking
    - Agent run lifecycle management (PENDING → RUNNING → COMPLETED/FAILED)
    """

    def __init__(self, session: Session):
        self._session = session
        self._agent_id: str = self.__class__.__name__
        self._llm_input: Optional[dict] = None
        self._llm_metrics: Dict[str, Any] = {}

    # --- LLMClientUser interface ---
    def get_agent_id(self) -> str:
        return self._agent_id

    def get_session_id(self) -> Optional[str]:
        return None

    def record_llm_cost(self, cost_usd: float, metadata: Dict[str, Any]) -> None:
        self._llm_metrics = metadata
        if 'llm_input' in metadata:
            self._llm_input = metadata['llm_input']

    def get_llm_metrics(self) -> Dict[str, Any]:
        return self._llm_metrics

    # --- LLM helpers ---
    def _create_llm_client(self) -> LLMClient:
        """Create an LLM client from application config."""
        llm_config = LLMConfig(
            provider=LLMProvider(config.LLM_PROVIDER),
            model_name=config.LLM_MODEL,
            api_key=config.LLM_API_KEY,
            api_base=getattr(config, 'LLM_API_BASE', None),
            api_version=getattr(config, 'LLM_API_VERSION', None),
            langfuse_public_key=config.LANGFUSE_PUBLIC_KEY if config.LLM_TRACING_ENABLED else None,
            langfuse_secret_key=config.LANGFUSE_SECRET_KEY if config.LLM_TRACING_ENABLED else None,
            langfuse_host=config.LANGFUSE_HOST if config.LLM_TRACING_ENABLED else None,
            enable_tracing=config.LLM_TRACING_ENABLED,
        )
        return LLMFactory.create_client(user=self, config=llm_config)

    def _load_prompt(self, prompt_name: str) -> PromptSchema:
        """Load a prompt by name using the configured prompt manager."""
        pm = PromptFactory.create_from_env()
        return pm.get(prompt_name)

    def _call_llm(self, prompt_name: str, variables: dict, response_model: Type[BaseModel]) -> BaseModel:
        """
        Load prompt, compile with variables, call LLM with structured output.

        Args:
            prompt_name: Prompt key (e.g., 'project_management/task_triage_agent')
            variables: Template variables for prompt compilation
            response_model: Pydantic model for structured output parsing

        Returns:
            Parsed response as the specified Pydantic model
        """
        prompt = self._load_prompt(prompt_name)
        message = LLMMessage.from_prompt(prompt, variables)
        client = self._create_llm_client()
        result = client.call_llm_structured(message, response_model)
        client.flush()
        return result

    # --- Abstract interface ---
    @abstractmethod
    def run(self, **kwargs) -> Optional[str]:
        """
        Execute the agent's main logic.

        Returns:
            agent_run_id if successful, None if skipped (e.g., no input data)
        """
        ...
```

**Key design decision**: `BaseAgent` does NOT manage its own AgentRun lifecycle (PENDING → RUNNING → COMPLETED/FAILED). That responsibility stays with the executor service, which wraps the agent run in a try/except and updates status. This keeps agents focused on business logic.

---

## Step 4: Agent Executor Service with Registry Pattern

### File: `src/common/services/agent_executor_service.py`

**Source**: `src/rcm/planner/services/agent_executor_service.py`

**Problem with current design**: The rcm version has a giant if/elif chain mapping `AgentType` enum values to specific agent classes. Not extensible.

**New design**: Registry pattern where domain modules register their agents at import time.

```python
# --- Agent Registry ---
_agent_registry: Dict[str, Type[BaseAgent]] = {}

def register_agent(agent_type: str, agent_class: Type[BaseAgent]) -> None:
    """Register an agent class for a given agent type string."""
    _agent_registry[agent_type] = agent_class

def get_registered_agent(agent_type: str) -> Type[BaseAgent]:
    """Look up a registered agent class. Raises KeyError if not found."""
    if agent_type not in _agent_registry:
        raise ValueError(f"Unknown agent type: {agent_type}. Registered: {list(_agent_registry.keys())}")
    return _agent_registry[agent_type]


# --- Executor ---
def execute_agent(
    tenant_id: str,
    bu_id: str,
    agent_type: str,
    input_params: Optional[dict],
    agent_run_id: str,
) -> str:
    """
    Execute a registered agent with full lifecycle tracking.

    Lifecycle:
        1. Mark agent run as RUNNING
        2. Instantiate agent class from registry
        3. Call agent.run(**input_params)
        4. Capture LLM metrics
        5. Mark COMPLETED or FAILED

    Uses a fresh DB session (not the request session).
    """
    db = DbSessionManager()

    # 1. Mark RUNNING
    with db.get_session(DbSessionType.WRITE) as session:
        service = AgentRunService(session)
        service.update_status(tenant_id, bu_id, agent_run_id, status='RUNNING', started_at=datetime.utcnow())

    # 2. Execute agent
    try:
        with db.get_session(DbSessionType.WRITE) as session:
            agent_class = get_registered_agent(agent_type)
            agent = agent_class(session)
            result = agent.run(tenant_id=tenant_id, bu_id=bu_id, agent_run_id=agent_run_id, **(input_params or {}))
            llm_metrics = agent.get_llm_metrics()

        # 3. Mark COMPLETED
        with db.get_session(DbSessionType.WRITE) as session:
            service = AgentRunService(session)
            service.update_status(
                tenant_id, bu_id, agent_run_id,
                status='COMPLETED',
                completed_at=datetime.utcnow(),
                output=result if isinstance(result, dict) else {'result': result},
                llm_cost_usd=llm_metrics.get('cost_usd'),
                llm_latency_ms=llm_metrics.get('latency_ms'),
                llm_metadata=llm_metrics,
            )

    except Exception as e:
        # 4. Mark FAILED
        with db.get_session(DbSessionType.WRITE) as session:
            service = AgentRunService(session)
            service.update_status(
                tenant_id, bu_id, agent_run_id,
                status='FAILED',
                completed_at=datetime.utcnow(),
                error_message=str(e),
            )
        raise

    return agent_run_id
```

**Registration pattern** — domain modules register agents in their `__init__.py`:
```python
# src/project_management/agents/__init__.py
from src.common.services.agent_executor_service import register_agent
from src.project_management.agents.task_triage_agent import TaskTriageAgent

register_agent('task_triage', TaskTriageAgent)
```

**Verification**: `execute_agent('task_triage', ...)` resolves to `TaskTriageAgent`, runs it, and tracks lifecycle.

---

## Step 5: Context Builder Pattern (Generic)

### File: `src/common/services/base_context.py`

**Source pattern**: `src/rcm/planner/services/lot_planner_context.py`

The rcm context builders use frozen Pydantic models with pre-computed lookup tables. This is the right pattern — document it and provide a minimal base.

```python
from pydantic import BaseModel


class BaseAgentContext(BaseModel):
    """
    Base class for agent context objects.

    Context objects are immutable snapshots of all data an agent needs.
    They are built once by a ContextBuilder, then consumed by the agent.

    Pattern:
    - Inherit from BaseAgentContext with model_config = ConfigDict(frozen=True)
    - Include raw data fields and pre-computed lookup dictionaries
    - Builder class fetches from DB and constructs the context
    - Agent receives context — no scattered DB access during execution
    """
    model_config = ConfigDict(frozen=True)

    tenant_id: str
    bu_id: str
```

**No abstract builder base class** — builders are simple enough that they don't need a framework. Each agent defines its own context dataclass and builder. The pattern is documented, not enforced via inheritance.

**Example structure** (for TaskTriageAgent):
```python
class TaskTriageContext(BaseAgentContext):
    """Immutable context for TaskTriageAgent."""
    model_config = ConfigDict(frozen=True)

    task: TaskSchema
    project: ProjectSchema
    sibling_tasks: tuple[TaskSchema, ...]
    label_map: dict[str, LabelSchema]  # pre-computed lookup


class TaskTriageContextBuilder:
    """Builds TaskTriageContext from DB data."""

    def __init__(self, session: Session):
        self._task_service = TaskService(session)
        self._project_service = ProjectService(session)
        self._label_service = LabelService(session)

    def build(self, tenant_id: str, bu_id: str, task_id: str) -> TaskTriageContext:
        task = self._task_service.get_entity_by_id(...)
        project = self._project_service.get_entity_by_id(...)
        sibling_tasks = self._task_service.list_entities(...)
        labels = self._label_service.list_entities(...)
        label_map = {l.id: l for l in labels}

        return TaskTriageContext(
            tenant_id=tenant_id,
            bu_id=bu_id,
            task=task,
            project=project,
            sibling_tasks=tuple(sibling_tasks),
            label_map=label_map,
        )
```

---

## Step 6: Post-LLM Pipeline Pattern

The post-LLM pipeline is not a framework — it's a pattern demonstrated in the example agent. Each agent implements these stages in its `run()` method:

### Stages

1. **Structured output parsing** — handled by `_call_llm(response_model=...)` which returns a typed Pydantic model
2. **Post-validation** — agent validates LLM output against business rules (e.g., priorities sum to 100%, labels exist)
3. **Post-enrichment** — agent adds computed fields (e.g., latency_ms, matched label IDs, derived scores)
4. **Persistence** — agent saves results to DB via service layer

### File: `src/common/services/post_llm_pipeline.py`

Provide lightweight helpers, not a framework:

```python
from pydantic import BaseModel, ValidationError
from typing import Type, Optional


class PostValidationError(Exception):
    """Raised when LLM output fails post-validation."""
    def __init__(self, message: str, validation_errors: Optional[list] = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


def validate_llm_output(output: BaseModel, validators: list[callable]) -> list[str]:
    """
    Run a list of validator functions against parsed LLM output.

    Each validator returns None on success or a string error message on failure.
    Returns list of error messages (empty = valid).
    """
    errors = []
    for validator_fn in validators:
        error = validator_fn(output)
        if error:
            errors.append(error)
    return errors
```

**Design decision**: No abstract pipeline class. Agents call `_call_llm()` → validate → enrich → persist in their `run()` method. This avoids over-abstraction while keeping the pattern clear.

---

## Step 7: Example Agent — `TaskTriageAgent`

### Files

| File | Description |
|------|-------------|
| `src/project_management/agents/__init__.py` | Register TaskTriageAgent |
| `src/project_management/agents/task_triage_agent.py` | Agent implementation |
| `src/project_management/agents/task_triage_context.py` | Context + builder |
| `src/project_management/agents/task_triage_schemas.py` | LLM response schemas |
| `prompts/project_management/task_triage_agent.md` | Prompt template |
| `prompts/project_management/task_triage_agent.meta.jsonc` | Prompt metadata |

### Agent: `TaskTriageAgent`

**Purpose**: Given a Task, analyze it and suggest: priority level, estimated effort, suggested labels, and a brief analysis.

```python
class TaskTriageAgent(BaseAgent):
    """
    Triages a task by analyzing its title, description, and project context.

    Pipeline:
        1. Build context (task + project + sibling tasks + labels)
        2. Load and compile prompt
        3. Call LLM with structured output
        4. Validate output (priority in valid range, labels exist)
        5. Enrich output (add label names, compute confidence)
        6. Persist triage result to task metadata
    """

    def __init__(self, session: Session):
        super().__init__(session)
        self._agent_id = 'task_triage_agent'

    def run(
        self,
        tenant_id: str,
        bu_id: str,
        task_id: str,
        agent_run_id: Optional[str] = None,
        **kwargs,
    ) -> Optional[dict]:
        # 1. Build context
        builder = TaskTriageContextBuilder(self._session)
        context = builder.build(tenant_id, bu_id, task_id)

        # 2. Prepare prompt variables
        variables = {
            'task_title': context.task.title,
            'task_description': context.task.description or '',
            'project_name': context.project.name,
            'project_description': context.project.description or '',
            'existing_labels': ', '.join(l.name for l in context.label_map.values()),
            'sibling_task_count': str(len(context.sibling_tasks)),
        }

        # 3. Call LLM
        result: TaskTriageResponse = self._call_llm(
            prompt_name='project_management/task_triage_agent',
            variables=variables,
            response_model=TaskTriageResponse,
        )

        # 4. Post-validate
        errors = validate_llm_output(result, [
            lambda r: None if 1 <= r.suggested_priority <= 5 else f"Priority {r.suggested_priority} out of range [1-5]",
            lambda r: None if r.estimated_hours > 0 else "Estimated hours must be positive",
        ])
        if errors:
            raise PostValidationError(f"Triage validation failed: {errors}", errors)

        # 5. Post-enrich
        enriched = {
            'suggested_priority': result.suggested_priority,
            'estimated_hours': result.estimated_hours,
            'suggested_labels': result.suggested_labels,
            'analysis': result.analysis,
            'confidence_score': result.confidence_score,
            'agent_run_id': agent_run_id,
        }

        # 6. Persist (update task metadata)
        task_service = TaskService(self._session)
        # Store triage result in task's metadata or a dedicated field
        # (exact persistence depends on Task entity design from Phase 3)

        return enriched
```

### LLM Response Schema: `task_triage_schemas.py`

```python
class TaskTriageResponse(BaseModel):
    """Structured output from LLM for task triage."""
    suggested_priority: int = Field(ge=1, le=5, description="Priority 1 (highest) to 5 (lowest)")
    estimated_hours: float = Field(gt=0, description="Estimated effort in hours")
    suggested_labels: list[str] = Field(default_factory=list, description="Suggested label names")
    analysis: str = Field(description="Brief analysis of the task")
    confidence_score: float = Field(ge=0, le=1, description="Confidence in the triage (0-1)")
```

### Prompt: `prompts/project_management/task_triage_agent.md`

```markdown
You are a project management assistant that triages tasks.

## Task to Triage
- **Title**: {{task_title}}
- **Description**: {{task_description}}

## Project Context
- **Project**: {{project_name}}
- **Project Description**: {{project_description}}
- **Available Labels**: {{existing_labels}}
- **Sibling Tasks in Project**: {{sibling_task_count}}

## Your Job
Analyze this task and provide:
1. **Suggested Priority** (1=critical, 5=nice-to-have)
2. **Estimated Hours** of effort
3. **Suggested Labels** from the available labels (or suggest new ones)
4. **Analysis** — a 2-3 sentence explanation of your triage reasoning
5. **Confidence Score** (0.0 to 1.0) — how confident you are in this triage
```

### Prompt Metadata: `prompts/project_management/task_triage_agent.meta.jsonc`

```jsonc
{
  "prompt_key": "project_management/task_triage_agent",
  "prompt_type": "text",
  "content_file": "task_triage_agent.md",
  "version": "1",
  "labels": ["latest"],
  "config": {
    "model": "gpt-4",
    "temperature": 0.3
  }
}
```

---

## Step 8: Agent Registration and Wiring

### File: `src/project_management/agents/__init__.py`

```python
from src.common.services.agent_executor_service import register_agent
from src.project_management.agents.task_triage_agent import TaskTriageAgent

register_agent('task_triage', TaskTriageAgent)
```

### File: `main.py` updates

Add agent run router and ensure agent module is imported (to trigger registration):

```python
# Import to trigger agent registration
import src.project_management.agents  # noqa: F401

# Add router
from src.common.controllers.agent_run_controller import router as agent_run_router
app.include_router(agent_run_router)
```

---

## Step 9: CLI Commands for Agent Operations

### File: `src/dev_tools/cli.py` additions

Add generic agent commands alongside existing ones:

```python
@main_group.command()
@click.argument('agent_type')
@click.option('--tenant-id', required=True)
@click.option('--bu-id', required=True)
@click.option('--params', default='{}', help='JSON input params')
def run_agent(agent_type: str, tenant_id: str, bu_id: str, params: str):
    """Run any registered agent by type."""
    import json
    from src.common.services.agent_executor_service import execute_agent
    from src.common.services.agent_run_service import AgentRunService
    from src.shared.infra.db.db_session_manager import DbSessionManager, DbSessionType

    input_params = json.loads(params)
    db = DbSessionManager()

    # Create agent run record
    with db.get_session(DbSessionType.WRITE) as session:
        service = AgentRunService(session)
        run = service.create_agent_run(tenant_id, bu_id, agent_type, input_params)
        agent_run_id = run.id

    # Execute
    result_id = execute_agent(tenant_id, bu_id, agent_type, input_params, agent_run_id)
    click.echo(f"Agent run completed: {result_id}")
```

Also keep existing prompt management commands (`pm` group).

---

## Step 10: Agent Tests

### Test Files

| File | Layer | What it Tests |
|------|-------|---------------|
| `tests/common/repositories/test_agent_run_repository.py` | Repository | CRUD, filters, pagination on AgentRunEntity (SQLite) |
| `tests/common/services/test_agent_run_service.py` | Service | create_agent_run, update_status, list with mocked repo |
| `tests/common/controllers/test_agent_run_controller.py` | Controller | HTTP endpoints with mocked service |
| `tests/project_management/agents/test_task_triage_agent.py` | Agent | Full pipeline with mocked LLM |
| `tests/integration/test_agent_run_integration.py` | Integration | End-to-end agent invocation (PostgreSQL) |

### Agent Test Pattern: `test_task_triage_agent.py`

```python
class TestTaskTriageAgent:
    """Tests for TaskTriageAgent with mocked LLM."""

    def test_successful_triage(self, db_session, seeded_task, seeded_project):
        """Agent triages a task and returns valid structured output."""
        mock_response = TaskTriageResponse(
            suggested_priority=2,
            estimated_hours=4.0,
            suggested_labels=['bug', 'backend'],
            analysis='This task involves fixing a backend API bug.',
            confidence_score=0.85,
        )

        agent = TaskTriageAgent(db_session)

        with patch.object(agent, '_call_llm', return_value=mock_response):
            result = agent.run(
                tenant_id=seeded_task.tenant_id,
                bu_id=seeded_task.bu_id,
                task_id=seeded_task.id,
            )

        assert result is not None
        assert result['suggested_priority'] == 2
        assert result['estimated_hours'] == 4.0
        assert result['confidence_score'] == 0.85

    def test_invalid_priority_fails_validation(self, db_session, seeded_task, seeded_project):
        """Post-validation catches out-of-range priority from LLM."""
        mock_response = TaskTriageResponse(
            suggested_priority=10,  # Invalid
            estimated_hours=4.0,
            suggested_labels=[],
            analysis='Test',
            confidence_score=0.5,
        )

        agent = TaskTriageAgent(db_session)

        with patch.object(agent, '_call_llm', return_value=mock_response):
            with pytest.raises(PostValidationError):
                agent.run(
                    tenant_id=seeded_task.tenant_id,
                    bu_id=seeded_task.bu_id,
                    task_id=seeded_task.id,
                )

    def test_lifecycle_state_transitions(self, db_session, seeded_task, seeded_project):
        """Agent executor manages PENDING → RUNNING → COMPLETED transitions."""
        mock_response = TaskTriageResponse(
            suggested_priority=3,
            estimated_hours=2.0,
            suggested_labels=[],
            analysis='Simple task.',
            confidence_score=0.9,
        )

        # Create agent run
        service = AgentRunService(db_session)
        run = service.create_agent_run(
            seeded_task.tenant_id, seeded_task.bu_id, 'task_triage', {'task_id': seeded_task.id}
        )
        assert run.status == 'PENDING'

        # Execute (mocked)
        with patch.object(TaskTriageAgent, '_call_llm', return_value=mock_response):
            execute_agent(
                seeded_task.tenant_id, seeded_task.bu_id,
                'task_triage', {'task_id': seeded_task.id}, run.id,
            )

        # Verify COMPLETED
        updated = service.get_entity_by_id(...)
        assert updated.status == 'COMPLETED'
        assert updated.completed_at is not None

    def test_failed_agent_marks_failed(self, db_session, seeded_task, seeded_project):
        """Agent failure is captured in agent run record."""
        agent = TaskTriageAgent(db_session)

        with patch.object(agent, '_call_llm', side_effect=Exception('LLM timeout')):
            # execute_agent should catch and mark FAILED
            ...
```

---

## Step 11: Alembic Migration

### New migration for `agent_run` table

Generate migration after entity is in place:

```bash
alembic revision --autogenerate -m "add_generic_agent_run_table"
```

**Table**: `agent_run`
**Columns**: id, tenant_id, bu_id, agent_type, status, input_params, output, error_message, started_at, completed_at, llm_input, llm_output, llm_cost_usd, llm_latency_ms, llm_metadata, created_at, updated_at, deleted_at, archived_at, created_by, updated_by, is_active, version, source, notes

**Indexes**:
- `ix_agent_run_tenant_bu` on (tenant_id, bu_id)
- `ix_agent_run_agent_type` on (agent_type)
- `ix_agent_run_status` on (status)

---

## File Inventory (New / Modified)

### New Files
| File | Type | Description |
|------|------|-------------|
| `src/common/entities/agent_run_entity.py` | Entity | Generic AgentRunEntity |
| `src/common/schemas/agent_run_schema.py` | Schemas | All CRUD schemas for AgentRun |
| `src/common/repositories/agent_run_repository.py` | Repository | AgentRunRepository |
| `src/common/services/agent_run_service.py` | Service | AgentRunService with lifecycle methods |
| `src/common/controllers/agent_run_controller.py` | Controller | REST endpoints for agent runs |
| `src/common/services/base_agent.py` | Base class | Generic BaseAgent (from BasePlannerAgent) |
| `src/common/services/agent_executor_service.py` | Executor | Registry-based agent executor |
| `src/common/services/base_context.py` | Base class | BaseAgentContext documentation |
| `src/common/services/post_llm_pipeline.py` | Helpers | Post-validation utilities |
| `src/project_management/agents/__init__.py` | Registration | Agent registration |
| `src/project_management/agents/task_triage_agent.py` | Agent | Example agent implementation |
| `src/project_management/agents/task_triage_context.py` | Context | Context + builder for triage |
| `src/project_management/agents/task_triage_schemas.py` | Schemas | LLM response model |
| `prompts/project_management/task_triage_agent.md` | Prompt | Triage prompt template |
| `prompts/project_management/task_triage_agent.meta.jsonc` | Metadata | Prompt config |
| `tests/common/repositories/test_agent_run_repository.py` | Test | Repository layer tests |
| `tests/common/services/test_agent_run_service.py` | Test | Service layer tests |
| `tests/common/controllers/test_agent_run_controller.py` | Test | Controller layer tests |
| `tests/project_management/agents/test_task_triage_agent.py` | Test | Agent pipeline tests |
| `tests/integration/test_agent_run_integration.py` | Test | Integration tests |
| `migrations/versions/xxx_add_generic_agent_run.py` | Migration | Alembic migration |

### Modified Files
| File | Change |
|------|--------|
| `src/shared/config/config.py` | Add `LLM_TRACING_ENABLED` |
| `src/dev_tools/cli.py` | Add generic `run-agent` command |
| `main.py` | Add agent_run_router, import agent registration |
| `src/common/entities/__init__.py` | Export `AgentRunEntity` |

### Unchanged (Already Generic)
| File | Status |
|------|--------|
| `src/utilities/llm_manager/*` | Keep as-is — already generic |
| `src/utilities/prompt_manager/*` | Keep as-is — already generic |
| `src/shared/infra/db/db_session_manager.py` | Keep as-is |
| `src/shared/common/nanoids.py` | Keep as-is |

---

## Execution Order

```
Step 1: Config toggle (LLM_TRACING_ENABLED)
  → verify: config loads, tracing disabled by default
Step 2: AgentRun MVCS (entity → schema → repo → service → controller)
  → verify: CRUD endpoints work, precommit-tests pass
Step 3: BaseAgent generalization
  → verify: imports clean, no rcm references
Step 4: Agent executor with registry
  → verify: register_agent + execute_agent work end-to-end
Step 5: Context builder pattern (base + example)
  → verify: TaskTriageContext builds correctly
Step 6: Post-LLM pipeline helpers
  → verify: validate_llm_output works
Step 7: TaskTriageAgent implementation
  → verify: agent runs with mocked LLM
Step 8: Wiring (registration, main.py, routing)
  → verify: POST /agent-runs invokes TaskTriageAgent
Step 9: CLI commands
  → verify: `run-agent task_triage --tenant-id ... --bu-id ...` works
Step 10: Tests (all layers)
  → verify: precommit-tests passes, agent tests pass without LLM
Step 11: Alembic migration
  → verify: upgrade/downgrade cycle works
```

---

## Design Decisions

1. **No abstract pipeline framework** — agents implement the 4-stage post-LLM pipeline in their `run()` method directly. A framework would be over-abstraction for a reference repo.

2. **Registry pattern over enum mapping** — domain modules register agents at import time. More extensible than the rcm approach of a centralized if/elif chain.

3. **BaseAgent does not own lifecycle** — the executor service manages PENDING → RUNNING → COMPLETED/FAILED. Agents focus on business logic and return results.

4. **Context builder is a pattern, not a base class** — `BaseAgentContext` provides `tenant_id`/`bu_id` and documents the frozen-model convention. No abstract builder class.

5. **LLM client and prompt manager unchanged** — they are already generic in `src/utilities/`. No refactoring needed.

6. **`output` field added to AgentRunEntity** — the rcm version lacks a generic output field (it uses relationships instead). The generic version stores output as JSON.

7. **`LLM_TRACING_ENABLED` independent of prompt source** — tracing to Langfuse is decoupled from where prompts are loaded. Both can be on, both off, or any combination.

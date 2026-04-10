# Phase 6b: TaskTriageAgent + Agent Tests

## Execution Context
**Depends on**: Phase 6a (BaseAgent, AgentRun MVCS, executor, registry)
**Blocks**: Phase 7
**Parallel with**: Phase 5b (auth mocking + agent test patterns)

## Goal
Build the example TaskTriageAgent demonstrating the full agent pipeline: context build -> prompt -> LLM -> validate -> enrich -> persist. Write agent tests with mocked LLM.

## Critical Reconciliation Decisions (Baked In)
- **I4**: Agent lives at `src/project_mgmt/agents/task_triage/` (NOT `project_management`)
- **I7**: Registers via `register_agent('task_triage', TaskTriageAgent)` — single registry from Phase 6a

## Pre-Conditions
- Phase 6a DONE: BaseAgent, AgentRun MVCS, executor service, registry pattern
- Phase 3 DONE: Task, Project, Label entities exist
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- TaskTriageAgent demonstrates full pipeline
- Agent tests pass without live LLM calls (mocked `_call_llm`)
- Prompt file exists at `prompts/project_mgmt/task_triage_agent.md`
- Agent registered and invocable via executor

---

## Step 1: Agent Directory Structure

```
src/project_mgmt/
  agents/
    __init__.py                        # register_agent('task_triage', TaskTriageAgent)
    task_triage/
      __init__.py
      task_triage_agent.py             # Agent implementation
      task_triage_context.py           # Context dataclass + builder
      task_triage_schemas.py           # LLM response model

prompts/project_mgmt/
  task_triage_agent.md                 # Prompt template
  task_triage_agent.meta.jsonc         # Prompt metadata
```

---

## Step 2: Context Builder

### File: `src/project_mgmt/agents/task_triage/task_triage_context.py`

```python
class TaskTriageContext(BaseAgentContext):
    """Immutable context for TaskTriageAgent."""
    model_config = ConfigDict(frozen=True)

    task: TaskSchema
    project: ProjectSchema
    sibling_tasks: tuple[TaskSchema, ...]
    label_map: dict[str, LabelSchema]

class TaskTriageContextBuilder:
    def __init__(self, session: Session):
        self._task_service = TaskService(session)
        self._project_service = ProjectService(session)
        self._label_service = LabelService(session)

    def build(self, tenant_id, bu_id, task_id) -> TaskTriageContext:
        task = self._task_service.get_entity_by_id(...)
        project = self._project_service.get_entity_by_id(...)
        sibling_tasks = self._task_service.list_entities(project_id=task.project_id, ...)
        labels = self._label_service.list_entities(...)
        label_map = {l.id: l for l in labels[0]}  # list_entities returns (items, count)

        return TaskTriageContext(
            tenant_id=tenant_id, bu_id=bu_id,
            task=task, project=project,
            sibling_tasks=tuple(sibling_tasks[0]),
            label_map=label_map,
        )
```

---

## Step 3: LLM Response Schema

### File: `src/project_mgmt/agents/task_triage/task_triage_schemas.py`

```python
class TaskTriageResponse(BaseModel):
    suggested_priority: int = Field(ge=1, le=5, description="1=highest, 5=lowest")
    estimated_hours: float = Field(gt=0)
    suggested_labels: list[str] = Field(default_factory=list)
    analysis: str = Field(description="2-3 sentence triage reasoning")
    confidence_score: float = Field(ge=0, le=1)
```

---

## Step 4: Agent Implementation

### File: `src/project_mgmt/agents/task_triage/task_triage_agent.py`

```python
class TaskTriageAgent(BaseAgent):
    def __init__(self, session: Session):
        super().__init__(session)
        self._agent_id = 'task_triage_agent'

    def run(self, tenant_id, bu_id, task_id, agent_run_id=None, **kwargs) -> Optional[dict]:
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
            prompt_name='project_mgmt/task_triage_agent',
            variables=variables,
            response_model=TaskTriageResponse,
        )

        # 4. Post-validate
        errors = validate_llm_output(result, [
            lambda r: None if 1 <= r.suggested_priority <= 5 else f"Priority {r.suggested_priority} out of range",
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

        # 6. Persist (store in agent run output, not directly on task)
        return enriched
```

---

## Step 5: Agent Registration

### File: `src/project_mgmt/agents/__init__.py`

```python
from common.services.agent_executor_service import register_agent
from project_mgmt.agents.task_triage.task_triage_agent import TaskTriageAgent

register_agent('task_triage', TaskTriageAgent)
```

### Wire in `main.py`
```python
import project_mgmt.agents  # noqa: F401 — triggers registration
```

---

## Step 6: Prompt Files

### File: `prompts/project_mgmt/task_triage_agent.md`

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

### File: `prompts/project_mgmt/task_triage_agent.meta.jsonc`
```jsonc
{
  "prompt_key": "project_mgmt/task_triage_agent",
  "prompt_type": "text",
  "content_file": "task_triage_agent.md",
  "version": "1",
  "labels": ["latest"],
  "config": {"model": "gpt-4", "temperature": 0.3}
}
```

---

## Step 7: Agent Tests

### File: `tests/project_mgmt/agents/test_task_triage_agent.py`

```python
class TestTaskTriageAgent:
    def test_successful_triage(self, db_session, seeded_task, seeded_project, seeded_labels):
        mock_response = TaskTriageResponse(
            suggested_priority=2, estimated_hours=4.0,
            suggested_labels=['bug', 'backend'],
            analysis='Backend API bug fix.', confidence_score=0.85,
        )
        agent = TaskTriageAgent(db_session)
        with patch.object(agent, '_call_llm', return_value=mock_response):
            result = agent.run(tenant_id=..., bu_id=..., task_id=...)
        assert result['suggested_priority'] == 2
        assert result['confidence_score'] == 0.85

    def test_invalid_priority_fails_validation(self, ...):
        mock_response = TaskTriageResponse(suggested_priority=10, ...)
        with pytest.raises(PostValidationError):
            agent.run(...)

    def test_lifecycle_state_transitions(self, ...):
        # Create agent run, execute via executor, verify PENDING -> RUNNING -> COMPLETED
        service = AgentRunService(db_session)
        run = service.create_agent_run(...)
        assert run.status == 'PENDING'
        with patch.object(TaskTriageAgent, '_call_llm', return_value=mock_response):
            execute_agent(...)
        updated = service.get_entity_by_id(...)
        assert updated.status == 'COMPLETED'

    def test_failed_agent_marks_failed(self, ...):
        # LLM raises exception -> agent run marked FAILED with error_message
```

---

## Files Summary

### Create (~8 files)
| File | Description |
|------|-------------|
| `src/project_mgmt/agents/__init__.py` | Agent registration |
| `src/project_mgmt/agents/task_triage/__init__.py` | Init |
| `src/project_mgmt/agents/task_triage/task_triage_agent.py` | Agent impl |
| `src/project_mgmt/agents/task_triage/task_triage_context.py` | Context + builder |
| `src/project_mgmt/agents/task_triage/task_triage_schemas.py` | LLM response model |
| `prompts/project_mgmt/task_triage_agent.md` | Prompt |
| `prompts/project_mgmt/task_triage_agent.meta.jsonc` | Prompt metadata |
| `tests/project_mgmt/agents/test_task_triage_agent.py` | Agent tests |

### Modify (~1 file)
| File | Change |
|------|--------|
| `main.py` | Add `import project_mgmt.agents` for registration |

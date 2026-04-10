# Task Triage Agent Writeup

## Goal

The TaskTriageAgent analyzes a task within a project context and provides intelligent triage recommendations. It helps project managers and team leads prioritize work by analyzing task descriptions, project context, and available labels to suggest priority, effort estimates, and applicable labels.

The agent answers: "Given this task in this project, what should its priority be, how much effort will it take, and what labels should apply?"

---

## User Input

Users trigger the agent with:
- **tenant_id** (string): Multi-tenant identifier
- **bu_id** (string): Business unit identifier
- **task_id** (string): The task to triage
- **agent_run_id** (optional string): Unique identifier for this run

---

## Agent Context (Data Fetched from DB)

The agent fetches and structures:

1. **Task Details**
   - task.id, title, description, project_id, status
   - Used to understand the work being triaged

2. **Project Context**
   - project.name, description, status
   - Provides domain context for the triage

3. **Sibling Tasks in Project**
   - All other tasks in the same project
   - Count is passed to LLM as context for scope awareness

4. **Available Labels**
   - All labels in the tenant/BU as a map (ID → LabelSchema)
   - Helps LLM suggest labels that actually exist
   - Also allows LLM to suggest new label names if needed

---

## LLM Input (Prompt Template: `prompts/project_mgmt/task_triage_agent.md`)

The agent calls the LLM with these variables:
- `{{task_title}}` — Task title
- `{{task_description}}` — Task description
- `{{project_name}}` — Project name
- `{{project_description}}` — Project description
- `{{existing_labels}}` — Comma-separated list of available label names
- `{{sibling_task_count}}` — Count of other tasks in same project (awareness of project scale)

**Prompt Instructs LLM to:**
1. Analyze the task in its project context
2. Provide 5 outputs (see Output section below)

---

## Output Schema

LLM produces a JSON response matching `TaskTriageResponse`:

```python
{
  "suggested_priority": int,          # 1=critical, 5=nice-to-have (range: 1-5)
  "estimated_hours": float,           # Hours of effort (must be > 0)
  "suggested_labels": list[str],      # Label names to apply (can be new or existing)
  "analysis": str,                    # 2-3 sentence reasoning (triage explanation)
  "confidence_score": float           # Confidence in this triage (range: 0.0-1.0)
}
```

---

## Output Field Classification

| Field | Type | LLM/Enriched/System |
|-------|------|---------------------|
| `suggested_priority` | int (1-5) | **LLM-produced** — requires judgment of task importance |
| `estimated_hours` | float | **LLM-produced** — requires estimation based on task analysis |
| `suggested_labels` | list[str] | **LLM-produced** — requires categorization judgment |
| `analysis` | str | **LLM-produced** — requires reasoning explanation |
| `confidence_score` | float | **LLM-produced** — requires self-assessment of reasoning quality |
| `agent_run_id` | str (optional) | **System-assigned** — passed through from input |

---

## Validation & Constraints

Post-LLM validation enforces:

### 1. **Priority Range**
- **Rule**: `1 <= suggested_priority <= 5`
- **Severity**: ERROR (raises PostValidationError if violated)
- **Rationale**: Priority must be on the 1-5 scale; 1=critical, 5=nice-to-have

### 2. **Effort Bounds**
- **Rule**: `estimated_hours > 0`
- **Severity**: ERROR (raises PostValidationError if violated)
- **Rationale**: Effort estimates must be positive; zero or negative effort is nonsensical

### 3. **Confidence Score Range**
- **Rule**: `0.0 <= confidence_score <= 1.0` (enforced in Pydantic schema)
- **Severity**: ERROR (validation error at response model level)
- **Rationale**: Confidence is a probability; must be between 0 and 1

### 4. **Labels Exist (No Validation)**
- **Current**: LLM can suggest any label names; no validation that they exist in the system
- **Note**: Post-processing code is responsible for creating new labels or mapping to existing ones

---

## Return Value

The agent returns a dict with all triage results:

```python
{
  'suggested_priority': int,
  'estimated_hours': float,
  'suggested_labels': list[str],
  'analysis': str,
  'confidence_score': float,
  'agent_run_id': optional[str],
}
```

---

## Constraints & Business Rules

1. **Task Must Exist**: If task_id not found, raises ValueError immediately
2. **Project Must Exist**: If project_id not found, raises ValueError immediately
3. **Priority Scale Fixed**: Only values 1-5 allowed; 1=most critical
4. **Effort Always Positive**: No zero or negative estimates
5. **Confidence 0-1**: Always a probability (0=no confidence, 1=certain)
6. **Analysis Required**: Must provide 2-3 sentence explanation for every triage
7. **Context Immutable**: TaskTriageContext is frozen (Pydantic ConfigDict frozen=True)

---

## Implementation Notes

### Context Builder Pattern
- `TaskTriageContextBuilder.build()` fetches all required data in sequence
- Returns immutable `TaskTriageContext` dataclass
- All services called via dependency injection (Session passed to __init__)

### Post-LLM Validation
- Uses `validate_llm_output()` utility with list of validation lambdas
- Each lambda returns list of error strings (empty if valid)
- All validators run; all errors collected and raised at once

### Prompt Model Config
- Uses GPT-4 (per `.meta.jsonc`)
- Temperature: 0.3 (relatively deterministic; favors consistency over creativity)

### Multi-Tenancy
- All operations scoped to tenant_id + bu_id
- No cross-tenant data leakage

---

## Test Coverage

### Unit Tests (`tests/project_mgmt/agents/test_task_triage_agent.py`)

**Wiring Tests:**
- ✅ Agent ID correctly set to 'task_triage_agent'

**Happy Path:**
- ✅ Successful triage with valid LLM response
- ✅ Agent run ID passed through correctly
- ✅ Prompt variables constructed correctly (titles, labels, counts)
- ✅ All output fields returned in result dict

**Error Handling:**
- ✅ LLM exceptions propagate correctly

**Context & Schema Validation:**
- ✅ TaskTriageContext is immutable (frozen)
- ✅ Label map keyed correctly by label ID
- ✅ Response schema rejects priority out of range (1-5)
- ✅ Response schema rejects negative hours
- ✅ Response schema rejects confidence outside 0-1

---

## Example Scenario

**Input:**
- Task: "Fix login bug after password reset"
- Project: "Backend API"
- Available Labels: bug, backend, auth, urgent, feature

**LLM Output:**
```json
{
  "suggested_priority": 1,
  "estimated_hours": 4.0,
  "suggested_labels": ["bug", "auth"],
  "analysis": "Critical authentication bug affecting all users. Requires changes to password reset flow and session validation. High-priority fix.",
  "confidence_score": 0.92
}
```

**Agent Return:**
```python
{
  'suggested_priority': 1,
  'estimated_hours': 4.0,
  'suggested_labels': ['bug', 'auth'],
  'analysis': 'Critical authentication bug affecting all users. Requires changes to password reset flow and session validation. High-priority fix.',
  'confidence_score': 0.92,
  'agent_run_id': 'arn_xyz789' # if provided
}
```

---

## Known Limitations & Gaps

1. **No Label Validation**: LLM can suggest labels that don't exist; system must handle gracefully
2. **No Task-Label Conflict Check**: No validation that suggested labels make sense together
3. **No Sibling Task Analysis**: While count is passed to LLM, actual sibling task details aren't (could be enriched)
4. **No Historical Context**: Agent doesn't see how similar tasks were prioritized before
5. **No Integration Tests**: Only unit tests with mocked LLM; no real DB integration tests documented

---

## Future Enhancements

1. Add historical triage data to context (similar past tasks + their outcomes)
2. Add real integration tests against test DB
3. Add label existence validation or suggest closest matches
4. Add feedback loop to learn from triage corrections
5. Support for custom priority scales (currently hardcoded 1-5)

# Sub-Phase 1: Foundation Types — LLMToolResponse, SystemUser, Exports

**Goal:** system-ops
**Depends on:** Nothing (first sub-phase)
**Estimated effort:** 0.5 session (~1h)
**Source plan sections:** Changes 1, 2, 6

---

## Objective

Add two new types to the LLM manager module: `LLMToolResponse` (a Pydantic model for tool-calling responses) and `SystemUser` (a lightweight `LLMClientUser` for non-agent callers). Export both from `__init__.py`. Write unit tests for both.

## Context

- `LLMToolResponse` goes in `src/utilities/llm_manager/llm_schemas.py` alongside existing Pydantic schemas (`LLMConfig`, `LLMMetrics`, `LLMMessageMetadata`). Follows the same `BaseModel` + `Annotated[..., Field(...)]` convention used throughout the file.
- `SystemUser` goes in `src/utilities/llm_manager/llm_client_user.py` alongside the `LLMClientUser` ABC it implements. This is a simple concrete class — no dependencies beyond the module.
- Exports go in `src/utilities/llm_manager/__init__.py`, which currently exports all public types from the module.

## Tasks

1. **Add `LLMToolResponse` to `src/utilities/llm_manager/llm_schemas.py`:**
   ```python
   class LLMToolResponse(BaseModel):
       """Response from an LLM call that may include tool calls."""
       content: str = ""
       tool_calls: list[dict[str, Any]] = []  # Each: {"id": str, "name": str, "args": dict}

       @property
       def has_tool_calls(self) -> bool:
           return bool(self.tool_calls)
   ```
   - Add `from typing import Any` to the existing imports (already has `Optional`).
   - Place after `LLMMessageMetadata` at the end of the file.

2. **Add `SystemUser` to `src/utilities/llm_manager/llm_client_user.py`:**
   ```python
   class SystemUser(LLMClientUser):
       """Lightweight LLMClientUser for callers that don't extend BaseAgent."""
       def __init__(self, agent_id: str):
           self._agent_id = agent_id

       def get_agent_id(self) -> str:
           return self._agent_id

       def get_session_id(self) -> Optional[str]:
           return None
   ```
   - Place after the `LLMClientUser` class in the same file.

3. **Update exports in `src/utilities/llm_manager/__init__.py`:**
   - Add import: `from utilities.llm_manager.llm_schemas import LLMToolResponse` (add to existing import line)
   - Add import: `from utilities.llm_manager.llm_client_user import SystemUser` (add to existing import line)
   - Add `'LLMToolResponse'` and `'SystemUser'` to `__all__`

4. **Write tests in `tests/utilities/llm_manager/test_llm_tool_response.py`:**
   - `LLMToolResponse` with no tool_calls: `has_tool_calls` is `False`, `content` is `""`
   - `LLMToolResponse` with tool_calls: `has_tool_calls` is `True`
   - `LLMToolResponse` content preserved
   - `SystemUser.get_agent_id()` returns provided id
   - `SystemUser.get_session_id()` returns `None`

5. **Run existing tests** to confirm no regressions:
   ```bash
   pytest tests/utilities/llm_manager/ -v
   ```

## Files Modified

| File | Change |
|------|--------|
| `src/utilities/llm_manager/llm_schemas.py` | Add `LLMToolResponse` class |
| `src/utilities/llm_manager/llm_client_user.py` | Add `SystemUser` class |
| `src/utilities/llm_manager/__init__.py` | Add exports for both new types |
| `tests/utilities/llm_manager/test_llm_tool_response.py` | **New file** — unit tests |

## Completion Criteria

- [ ] `LLMToolResponse` is importable from `utilities.llm_manager`
- [ ] `SystemUser` is importable from `utilities.llm_manager`
- [ ] `LLMToolResponse().has_tool_calls` returns `False`
- [ ] `LLMToolResponse(tool_calls=[{"id": "1", "name": "f", "args": {}}]).has_tool_calls` returns `True`
- [ ] `SystemUser("search-agent").get_agent_id()` returns `"search-agent"`
- [ ] `SystemUser("search-agent").get_session_id()` returns `None`
- [ ] `pytest tests/utilities/llm_manager/ -v` passes (existing + new tests)

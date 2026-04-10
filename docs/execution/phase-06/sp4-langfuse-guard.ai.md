# Sub-Phase 4: Langfuse Guard Module

**Phase:** 6 — Code Cleanup for OSS
**Plan task:** 6D (Langfuse Default Off)
**Dependencies:** sp1
**Blocks:** sp5, sp6, sp8
**Can run in parallel with:** sp2, sp3

## Objective
Make Langfuse observability disabled by default. Create a guard module that provides no-op stubs when Langfuse is disabled. Update all 13 consumer files to use the guard instead of importing Langfuse directly.

## Context
- Read shared context: `docs/execution/phase-06/_shared_context.md`
- Read plan (6D section): `docs/plan/phase-06-code-cleanup.md`
- Read config: `backend/src/shared/config/config.py` — verify `LANGFUSE_ENABLED` field exists
- Read decision: `docs/decision/env-config-design.md` — `LANGFUSE_ENABLED=false` default

## Deliverables

### 1. Verify Config Has `LANGFUSE_ENABLED`

Check `backend/src/shared/config/config.py` for:
- `LANGFUSE_ENABLED` field with default `False`
- If missing, add it as a `bool` field defaulting to `False`

### 2. Create Guard Module: `backend/src/shared/utilities/langfuse_guard.py` (NEW)

```python
"""Langfuse guard — provides no-op stubs when Langfuse is disabled."""
import functools
from shared.config.config import backend_config


def observe(*args, **kwargs):
    """No-op @observe decorator when Langfuse is disabled."""
    if getattr(backend_config, 'LANGFUSE_ENABLED', False):
        from langfuse import observe as real_observe
        return real_observe(*args, **kwargs)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*a, **kw):
            return func(*a, **kw)
        return wrapper

    if args and callable(args[0]):
        return decorator(args[0])
    return decorator


def get_client():
    """Return Langfuse client when enabled, no-op context manager when disabled."""
    if getattr(backend_config, 'LANGFUSE_ENABLED', False):
        from langfuse import get_client as real_get_client
        return real_get_client()

    class _NoOpClient:
        """No-op Langfuse client stub."""
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def __getattr__(self, name):
            return lambda *a, **kw: self
        def trace(self, **kwargs):
            return self
        def span(self, **kwargs):
            return self
        def generation(self, **kwargs):
            return self

    return _NoOpClient()
```

Adjust the `_NoOpClient` API surface based on actual usage patterns found in the consumer files. The key requirement: any method chain that works with real Langfuse should work silently with the stub.

### 3. Update `@observe` Consumers (9 files)

Replace `from langfuse import observe` (or `from langfuse.decorators import observe`) with `from shared.utilities.langfuse_guard import observe` in:

1. `backend/src/linkedout/intelligence/tools/career_tool.py`
2. `backend/src/linkedout/intelligence/tools/vector_tool.py`
3. `backend/src/linkedout/intelligence/tools/web_tool.py`
4. `backend/src/linkedout/intelligence/tools/network_tool.py`
5. `backend/src/linkedout/intelligence/tools/company_tool.py`
6. `backend/src/linkedout/intelligence/tools/sql_tool.py`
7. `backend/src/linkedout/intelligence/tools/result_set_tool.py`
8. `backend/src/linkedout/intelligence/tools/intro_tool.py`
9. `backend/src/linkedout/intelligence/tools/profile_tool.py`

For each file: only change the import line. Do not modify any `@observe` decorator usage — the guard's `observe()` is a drop-in replacement.

### 4. Update `get_client` Consumers (2 files)

Replace `from langfuse import get_client` (or similar) with `from shared.utilities.langfuse_guard import get_client` in:

1. `backend/src/linkedout/intelligence/controllers/search_controller.py`
2. `backend/src/linkedout/intelligence/controllers/best_hop_controller.py`

### 5. Update Langfuse Agent Usage (1 file)

In `backend/src/linkedout/intelligence/agents/search_agent.py`:
- Find how Langfuse is used (likely `observe` or client-based tracing)
- Replace with guard import
- Ensure the agent works when Langfuse is disabled

### 6. Update Langfuse Explainer Usage (1 file)

In `backend/src/linkedout/intelligence/explainer/why_this_person.py`:
- Find Langfuse usage
- Replace with guard import

### 7. Scan for Other Langfuse Imports

```bash
grep -rn "from langfuse" backend/src/ --include="*.py"
grep -rn "import langfuse" backend/src/ --include="*.py"
```

Any matches not covered above must also be updated to use the guard.

## Verification
1. `grep -rn "from langfuse" backend/src/ --include="*.py" | grep -v langfuse_guard` returns zero matches (all imports go through guard)
2. `cd backend && LANGFUSE_ENABLED=false uv run python -c "from shared.utilities.langfuse_guard import observe, get_client; print('Guard imports OK')"` succeeds
3. `cd backend && LANGFUSE_ENABLED=false uv run python -c "from linkedout.intelligence.tools.vector_tool import VectorTool; print('Tool imports OK')"` succeeds (no Langfuse crash)
4. `cd backend && uv run ruff check src/shared/utilities/langfuse_guard.py` clean
5. `cd backend && uv run ruff check src/linkedout/intelligence/` no new errors

## Notes
- `langfuse` stays in `requirements.txt` — it's an optional dependency that only activates when `LANGFUSE_ENABLED=true`.
- The guard module uses lazy imports (`from langfuse import ...` inside `if` blocks) so the app never crashes if Langfuse keys are missing.
- Do NOT modify `utilities/prompt_manager/` — SJ decision Q2 says keep it.
- The no-op client needs to handle whatever method chains the consumer files actually use. Read each consumer file to understand the API surface before finalizing `_NoOpClient`.

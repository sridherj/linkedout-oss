# SP4: Standardize Logger Usage + Request Logging Enhancement

**Sub-Phase:** 4 of 7
**Tasks:** 3C (Standardize Logger Usage) + 3D (Backend Request Logging Enhancement)
**Complexity:** M + S = M
**Depends on:** SP1 (core logging framework + correlation IDs)
**Blocks:** SP5 (CLI + enrichment logging)

---

## Objective

Replace all direct `import logging` / `logging.getLogger(__name__)` calls across the codebase with the enhanced `get_logger()` from SP1, adding component bindings. Also enhance the backend request logging middleware with component binding and additional context.

---

## Context

Read `_shared_context.md` for project-level context.

**Key constraint:** Do NOT change existing log messages — only change the import and logger instantiation pattern. Existing behavior must be preserved.

---

## Tasks

### 1. Find and Replace All Direct logging Usage (3C)

Grep for all files using `import logging` or `logging.getLogger(__name__)` directly:

```bash
grep -rn "import logging" backend/src/ --include="*.py"
grep -rn "logging.getLogger" backend/src/ --include="*.py"
```

Replace with:
```python
from shared.utilities.logger import get_logger
logger = get_logger(__name__, component="<component>")
```

**Component mapping by directory:**
| Directory Pattern | Component |
|---|---|
| `backend/src/linkedout/enrichment_pipeline/*` | `"enrichment"` |
| `backend/src/linkedout/import_pipeline/*` | `"import"` |
| `backend/src/linkedout/intelligence/*` | `"backend"` |
| `backend/src/dev_tools/*` | `"cli"` |
| `backend/src/utilities/llm_manager/*` | `"backend"` |
| `backend/src/shared/*` | `"backend"` |
| All other `backend/src/*` | `"backend"` |

**Exceptions — do NOT modify:**
- `backend/src/shared/utilities/logger.py` itself (contains `_StdlibIntercept`)
- Test files (`tests/**`)

### 2. Enhance Request Logging Middleware (3D)

**File:** `backend/src/shared/utilities/request_logging_middleware.py`

- Bind component: `logger = get_logger('http.access', component='backend')`
- Correlation ID is already added in SP1 — verify it appears in log entries
- Log additional context: method, path, status, duration_ms, query params (redact sensitive params like `api_key`, `token`)
- Keep the existing format — just add component and correlation_id to extra fields

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/src/shared/utilities/request_logging_middleware.py` | Component binding, enhanced context logging |
| ~20 files with `import logging` | Replace with `get_logger()` + component binding |

## Files NOT to Modify
- `backend/src/shared/utilities/logger.py` (except `_StdlibIntercept` — leave as-is)
- Test files

---

## Verification

### Automated Checks

After completing all changes:

```bash
# Should return ZERO results (except _StdlibIntercept and test files)
grep -rn "import logging" backend/src/ --include="*.py" | grep -v "_StdlibIntercept" | grep -v "test_"
grep -rn "logging.getLogger" backend/src/ --include="*.py" | grep -v "_StdlibIntercept" | grep -v "test_"
```

### Manual Checks

- Run existing tests — all must pass with no behavior changes
- Start the backend, make an API request, verify:
  - Log entry appears in `backend.log` (not just console)
  - Entry includes `correlation_id` and `duration_ms`
  - Response has `X-Correlation-ID` header

---

## Acceptance Criteria

- [ ] Zero `import logging` or `logging.getLogger` calls remain in backend/src/ (except `_StdlibIntercept`)
- [ ] Every logger instance has a `component` binding matching its directory
- [ ] Existing tests still pass — behavior unchanged
- [ ] Request logging includes correlation_id, component, duration_ms
- [ ] No existing log messages were changed — only import/instantiation patterns

# Phase 7: Operational Scaffold & Cross-Cutting Concerns

## Execution Context
**Depends on**: ALL previous phases (2, 3, 4, 5a, 5b, 6a, 6b)
**Blocks**: Phase 8
**Parallel with**: Nothing — last feature phase

## Goal
CLI surface, reliability patterns, structured logging, composed config, Alembic migrations, skill/agent accuracy check, documentation.

## Critical Reconciliation Decisions (Baked In)
- **I6**: Composed config: `AppConfig(AuthConfig, LLMConfig, ReliabilityConfig, BaseSettings)` — NOT flat 32-field class
- **I7**: Phase 7 CLI uses Phase 6a's `_agent_registry` (does NOT create its own AGENT_REGISTRY)
- CLI entry point: `rcv2` (from pyproject.toml)
- Phase 7 does NOT add CLI commands that Phase 6 partially added — it does the full restructure

## Pre-Conditions
- Phases 2-6 DONE: All domain code, auth, tests, agent infra in place
- `precommit-tests` passes

## Post-Conditions (Definition of Done)
- `precommit-tests` passes
- CLI organized in Click groups: db, test, prompt, agent, dev
- All CLI commands have `--help` text
- Reliability: retry + timeout policies (tenacity-based, config-driven)
- Structured logging (JSON in prod, readable in dev)
- Composed config with multiple inheritance
- Fresh Alembic migration for all new entities
- Skills and agents reference correct conventions (bu_id, project_mgmt, plural routers)
- ARCHITECTURE.md or README walkthrough exists
- Tenancy swap guide documented

---

## Step 1: CLI Restructure

### File: `src/dev_tools/cli.py` (rewrite)

Replace flat structure with Click groups:

```python
@click.group()
def cli():
    """Reference Code V2 -- Development Tools"""

# db group: reset, seed, verify-seed, validate-orm
# test group: unit, integration, all
# prompt group: re-export from utilities/prompt_manager/cli.py (push, pull, list, diff)
# agent group: run <name>, list
# dev group: start
```

### Agent CLI — Use Phase 6a's Registry

```python
@agent.command(name='run')
@click.argument('agent_name')
@click.option('--tenant-id', required=True)
@click.option('--bu-id', required=True)
def agent_run(agent_name, tenant_id, bu_id):
    from common.services.agent_executor_service import get_registered_agent, _agent_registry
    # Import agent modules to trigger registration
    import project_mgmt.agents  # noqa
    # Look up and execute
    ...

@agent.command(name='list')
def agent_list():
    from common.services.agent_executor_service import _agent_registry
    import project_mgmt.agents  # noqa
    for name in _agent_registry:
        click.echo(f"  {name}")
```

### New File: `src/dev_tools/run_agent.py`

Thin wrapper that imports agent modules (triggering registration) and calls `execute_agent()`.

### Update `pyproject.toml`
```toml
[project.scripts]
rcv2 = "dev_tools.cli:cli"
```

Remove all linkedout-specific entry points.

### Verify
```bash
python -m dev_tools.cli --help
python -m dev_tools.cli db --help
python -m dev_tools.cli test --help
python -m dev_tools.cli prompt --help
python -m dev_tools.cli agent --help
python -m dev_tools.cli agent list
python -m dev_tools.cli dev --help
```

---

## Step 2: Reliability Infrastructure

### New Directory: `src/shared/infra/reliability/`

### `retry_policy.py` — Tenacity-based
```python
@dataclass
class RetryConfig:
    max_attempts: int = 3
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 60.0
    retryable_exceptions: tuple = (ConnectionError, TimeoutError)

LLM_RETRY_CONFIG = RetryConfig(max_attempts=3, min_wait_seconds=2.0, max_wait_seconds=30.0)
EXTERNAL_API_RETRY_CONFIG = RetryConfig(max_attempts=3, min_wait_seconds=1.0, max_wait_seconds=15.0)

def retry_with_policy(config: RetryConfig) -> decorator:
    """Config-driven retry decorator using tenacity."""
```

### `timeout_policy.py` — Signal-based
```python
@dataclass
class TimeoutConfig:
    timeout_seconds: float = 30.0

LLM_TIMEOUT_CONFIG = TimeoutConfig(timeout_seconds=120.0)
EXTERNAL_API_TIMEOUT_CONFIG = TimeoutConfig(timeout_seconds=30.0)

def timeout_with_policy(config: TimeoutConfig) -> decorator:
    """Signal-based timeout (Unix main thread only)."""
```

### `rate_limiter.py` — Token bucket
```python
@dataclass
class RateLimitConfig:
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000

class RateLimiter:
    def __init__(self, config: RateLimitConfig): ...
    def acquire(self, tokens: int = 1) -> None: ...
```

### Apply to LLM Client
Wrap `LangChainLLMClient.call_llm_structured()` with retry + timeout:
```python
@retry_with_policy(LLM_RETRY_CONFIG)
@timeout_with_policy(LLM_TIMEOUT_CONFIG)
def call_llm_structured(self, message, response_model): ...
```

---

## Step 3: Structured Logging

### File: `src/shared/utilities/logger.py` (enhance)

Add JSON logging for production:
```python
def setup_logging(environment: str = 'local', log_level: str = 'INFO'):
    if environment == 'prod':
        # JSON formatter: timestamp, level, logger, message, extras
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
    else:
        # Human-readable: timestamp level logger message
        logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s %(message)s', level=log_level)
```

### Request/Response Logging Middleware
```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Log: method, path, status, duration_ms
```

### Wire into `main.py`
```python
from shared.utilities.logger import setup_logging
setup_logging(environment=config.ENVIRONMENT, log_level=config.LOG_LEVEL)
app.add_middleware(RequestLoggingMiddleware)
```

---

## Step 4: Composed Config

### File: `src/shared/config/config.py` (restructure)

```python
class AuthConfig(BaseSettings):
    AUTH_ENABLED: bool = True
    FIREBASE_ENABLED: bool = True
    # ... (from Phase 4's auth/config.py — merge here)

class LLMConfig(BaseSettings):
    LLM_PROVIDER: str = 'openai'
    LLM_MODEL: str = 'gpt-4o'
    LLM_API_KEY: Optional[str] = None
    LLM_TRACING_ENABLED: bool = False
    PROMPT_FROM_LOCAL_FILE: bool = False
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    # ...

class ReliabilityConfig(BaseSettings):
    LLM_RETRY_MAX_ATTEMPTS: int = 3
    LLM_RETRY_MIN_WAIT: float = 2.0
    LLM_RETRY_MAX_WAIT: float = 30.0
    LLM_TIMEOUT_SECONDS: float = 120.0
    EXTERNAL_API_RETRY_MAX_ATTEMPTS: int = 3
    EXTERNAL_API_TIMEOUT_SECONDS: float = 30.0
    RATE_LIMIT_LLM_RPM: int = 60

class AppConfig(AuthConfig, LLMConfig, ReliabilityConfig, BaseSettings):
    ENVIRONMENT: str = 'local'
    DATABASE_URL: str
    DEBUG: bool = False
    LOG_LEVEL: str = 'INFO'
    # ... remaining config
```

Note: `AuthConfig` fields from `src/shared/auth/config.py` move here. The separate auth config file is removed or becomes a re-export.

---

## Step 5: Alembic Migrations

```bash
# Remove old rcm-specific migrations (they reference rcm tables)
# Generate fresh initial migration for current state
alembic revision --autogenerate -m "Initial schema: organization + project_mgmt + agent_run"
```

Verify:
```bash
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Update `migrations/env.py` to import all current entities (org + project_mgmt + agent_run).

---

## Step 6: Skill/Agent Accuracy Check

Verify all `.claude/agents/` and `.claude/skills/` files reference correct conventions:
- `bu_id` (NOT `workspace_id`)
- `project_mgmt` (NOT `project_management`)
- Plural router names (`labels_router`)
- Correct file paths pointing to `src/project_mgmt/` examples

Update any references that still point to rcm.

---

## Step 7: Documentation

### File: `ARCHITECTURE.md` (or README section)

Brief walkthrough of MVCS flow:
- How to add a new CRUD entity (Label example)
- How to add a non-trivial entity (Task example)
- How to add an AI agent (TaskTriage example)

### Tenancy Swap Guide

Short section: "How to replace `bu` with `workspace` or `app_user`":
1. Rename `TenantBuMixin` -> `TenantWorkspaceMixin`
2. Update column names, FK targets
3. Update URL paths
4. Update config/schema field names

---

## Step 8: dev_tools Cleanup

| File | Action |
|------|--------|
| `src/dev_tools/cli.py` | Full rewrite (Step 1) |
| `src/dev_tools/run_agent.py` | Create (thin wrapper) |
| `src/dev_tools/run_all_agents.py` | Delete (linkedout-specific) |
| `src/dev_tools/db/verify_seed.py` | Update entity imports |
| `src/dev_tools/db/validate_orm.py` | Update ALL_ENTITIES list |

---

## Files Summary

### Create (~10 files)
| File | Description |
|------|-------------|
| `src/shared/infra/reliability/__init__.py` | Reliability exports |
| `src/shared/infra/reliability/retry_policy.py` | Retry decorator |
| `src/shared/infra/reliability/timeout_policy.py` | Timeout decorator |
| `src/shared/infra/reliability/rate_limiter.py` | Rate limiter |
| `src/dev_tools/run_agent.py` | Agent runner wrapper |
| `ARCHITECTURE.md` | Developer walkthrough |
| `migrations/versions/xxx_initial_schema.py` | Fresh migration |

### Modify (~8 files)
| File | Change |
|------|--------|
| `src/dev_tools/cli.py` | Full rewrite into Click groups |
| `src/shared/config/config.py` | Composed config classes |
| `src/shared/utilities/logger.py` | JSON logging + setup_logging() |
| `main.py` | Logging middleware, setup_logging call |
| `pyproject.toml` | Update entry point to rcv2 |
| `migrations/env.py` | Update entity imports |
| `src/dev_tools/db/verify_seed.py` | Update entity refs |
| `src/dev_tools/db/validate_orm.py` | Update ALL_ENTITIES |

### Delete (~1 file)
| File | Reason |
|------|--------|
| `src/dev_tools/run_all_agents.py` | Terrantic-specific |

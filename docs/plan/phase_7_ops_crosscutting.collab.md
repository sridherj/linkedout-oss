# Phase 7: Operational Scaffold & Cross-Cutting Concerns — Detailed Execution Plan

## Overview

Polish the reference repo with a clean CLI surface, reliability patterns (retry, timeout, rate-limit), structured logging with agent-aware context, config cleanup, and Alembic migrations. This phase makes the repo usable as a template — not just correct internals, but discoverable, well-documented operational commands.

**Verification gate**: `precommit-tests` must pass at the end.

**Dependencies**: Phases 2-6 must be complete. All project_mgmt domain entities, auth, testing infra, and AI agent infrastructure are in place.

---

## Current State (from code review)

### CLI (`src/dev_tools/cli.py`)
- Click-based with `main_group`
- Has: `reset-db`, `seed-db`, `verify-seed`, `validate-orm`, `precommit-tests`, `visualizer`, `run-all-agents`
- Has 7 rcm planner agent subcommands (linkedout-specific — will be gone after Phase 3)
- Missing: `test run`, `test run-integration`, `prompt list/push/pull`, `agent run <name>`, `dev start`

### Config (`src/shared/config/config.py`)
- Pydantic BaseSettings with env file mapping: `.env.local`, `.env`, `.env.test`, `.env.prod`
- Has: DATABASE_URL, LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LANGFUSE_*, PROMPT_FROM_LOCAL_FILE, LOG_LEVEL
- Missing: AUTH_ENABLED, LLM_TRACING_ENABLED, retry/timeout config, FIREBASE_* config
- Flat `BaseConfig` — will keep it flat (cleaner than a class hierarchy for a reference repo)

### Alembic
- `alembic.ini` and `migrations/env.py` both functional
- `env.py` imports 24 rcm entities — needs replacement with project_mgmt entities after Phase 3

### Logging (`src/shared/utilities/logger.py`)
- Basic: `logging.basicConfig` with stdout handler, simple format string
- `get_logger(name)` and `set_level(level)` helpers
- Missing: JSON logging in prod, request/response logging middleware, agent execution logging

### Reliability
- No retry/timeout/rate-limit infrastructure exists
- LLM client (`src/utilities/llm_manager/llm_client.py`) has no built-in retry or timeout

---

## Configuration Variables Reference

All config variables managed by `BaseConfig` (flat, env-file-per-environment):

| Variable | Type | Default | Env File Override | Purpose |
|----------|------|---------|-------------------|---------|
| `ENVIRONMENT` | str | `local` | all | Environment selector (`local`, `dev`, `test`, `prod`) |
| `DATABASE_URL` | str | required | all | PostgreSQL/SQLite connection string |
| `DEBUG` | bool | `False` | `.env.local` | Enable debug mode |
| `LOG_LEVEL` | str | `INFO` | all | Python log level |
| `DB_ECHO_LOG` | bool | `False` | `.env.local` | SQLAlchemy query echo |
| `BINDING_HOST` | str | `0.0.0.0` | all | FastAPI bind host |
| `BACKEND_HOST` | str | `localhost` | all | Public hostname |
| `BACKEND_PORT` | int | `8000` | all | FastAPI port |
| `BACKEND_SERVER_PROTOCOL` | str | `http` | `.env.prod` | Protocol for URL construction |
| `AUTH_ENABLED` | bool | `True` | `.env.local`=False, `.env.test`=False | Enable/disable auth |
| `FIREBASE_ENABLED` | bool | `True` | `.env.local`=False | Firebase auth provider |
| `FIREBASE_PROJECT_ID` | str | `''` | `.env.prod` | Firebase project |
| `FIREBASE_CREDENTIALS_PATH` | str | `''` | `.env.prod` | Path to Firebase credentials JSON |
| `LLM_PROVIDER` | str | `openai` | all | LLM provider (`openai`, `azure_openai`) |
| `LLM_MODEL` | str | `gpt-4o` | all | Model name |
| `LLM_API_KEY` | str? | `None` | `.env.local`, `.env.prod` | API key for LLM provider |
| `LLM_API_BASE` | str? | `None` | `.env.local` | Azure OpenAI base URL |
| `LLM_API_VERSION` | str? | `None` | `.env.local` | Azure API version |
| `OPENAI_API_KEY` | str? | `None` | `.env.local` | OpenAI fallback key |
| `PROMPT_FROM_LOCAL_FILE` | bool | `False` | `.env.local`=True, `.env.test`=True | Load prompts from local files vs Langfuse |
| `LLM_TRACING_ENABLED` | bool | `False` | `.env.prod`=True | Send traces to Langfuse |
| `LANGFUSE_PUBLIC_KEY` | str? | `None` | `.env.local`, `.env.prod` | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | str? | `None` | `.env.local`, `.env.prod` | Langfuse secret key |
| `LANGFUSE_HOST` | str? | `None` | `.env.local`, `.env.prod` | Langfuse host URL |
| `PROMPTS_DIRECTORY` | str | `prompts` | — | Local prompt files directory |
| `PROMPT_CACHE_TTL_SECONDS` | int | `300` | — | Prompt cache TTL |
| `LLM_RETRY_MAX_ATTEMPTS` | int | `3` | `.env.prod` | Max retry attempts for LLM calls |
| `LLM_RETRY_MIN_WAIT` | float | `2.0` | — | Min wait between LLM retries (seconds) |
| `LLM_RETRY_MAX_WAIT` | float | `30.0` | — | Max wait between LLM retries (seconds) |
| `LLM_TIMEOUT_SECONDS` | float | `120.0` | `.env.prod` | Timeout for LLM calls |
| `EXTERNAL_API_RETRY_MAX_ATTEMPTS` | int | `3` | — | Max retry attempts for external API calls |
| `EXTERNAL_API_TIMEOUT_SECONDS` | float | `30.0` | — | Timeout for external API calls |
| `RATE_LIMIT_LLM_RPM` | int | `60` | `.env.prod` | LLM requests per minute limit |
| `RATE_LIMIT_LLM_TPM` | int | `100000` | `.env.prod` | LLM tokens per minute limit |

---

## Step 1: Restructure CLI with Click Groups

### File: `src/dev_tools/cli.py` (rewrite)

**Current**: Flat command structure with all commands on `main_group`, plus linkedout-specific agent imports.

**After**: Organized into Click groups for discoverability. All linkedout references removed.

```python
import click


@click.group()
def cli():
    """Reference Code V2 -- Development Tools"""
    pass


# -- db group --
@cli.group()
def db():
    """Database management commands."""
    pass


@db.command(name='reset')
@click.option('--mode', type=click.Choice(['truncate', 'drop', 'reset']), default='truncate')
@click.option('--seed/--no-seed', default=True, help='Auto-seed after reset')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
def db_reset(mode, seed, yes):
    """Reset the database (truncate, drop tables, or full reset)."""
    from dev_tools.db.reset_db import run_reset
    mode_map = {'truncate': '1', 'drop': '2', 'reset': '3'}
    run_reset(mode_map[mode], auto_seed=seed, confirm=not yes)


@db.command(name='seed')
def db_seed():
    """Seed the database with sample data."""
    from dev_tools.db.seed import main as seed_main
    seed_main()


@db.command(name='verify-seed')
def db_verify_seed():
    """Verify seed data integrity."""
    from dev_tools.db.verify_seed import verify_seed
    success = verify_seed()
    if not success:
        raise SystemExit(1)


@db.command(name='validate-orm')
def db_validate_orm():
    """Validate SQLAlchemy ORM mappings against database."""
    from dev_tools.db.validate_orm import main as validate_main
    validate_main()


# -- test group --
@cli.group()
def test():
    """Test execution commands."""
    pass


@test.command(name='unit')
@click.option('--verbose', '-v', is_flag=True)
@click.option('--parallel/--no-parallel', default=True, help='Run with xdist')
def test_unit(verbose, parallel):
    """Run unit tests (SQLite, no PostgreSQL required)."""
    import subprocess
    cmd = ['pytest', 'tests/', '-k', 'not integration and not live_llm', '--tb=short']
    if verbose:
        cmd.append('-v')
    if parallel:
        cmd.extend(['-n', 'auto'])
    raise SystemExit(subprocess.run(cmd).returncode)


@test.command(name='integration')
@click.option('--verbose', '-v', is_flag=True)
def test_integration(verbose):
    """Run integration tests (requires PostgreSQL)."""
    import subprocess
    cmd = ['pytest', 'tests/integration/', '-m', 'integration and not live_llm', '--tb=short']
    if verbose:
        cmd.append('-v')
    raise SystemExit(subprocess.run(cmd).returncode)


@test.command(name='all')
def test_all():
    """Run full precommit test suite (unit + integration + live_llm)."""
    import subprocess
    stages = [
        ('Unit tests', ['pytest', 'tests/', '-k', 'not integration and not live_llm', '-q', '--tb=short']),
        ('Integration tests', ['pytest', 'tests/integration/', '-m', 'integration and not live_llm', '-q', '--tb=short']),
        ('Live LLM tests', ['pytest', 'tests/', '-m', 'live_llm', '-q', '--tb=short']),
    ]
    for label, cmd in stages:
        click.echo(f'\n=== {label} ===')
        result = subprocess.run(cmd)
        if result.returncode != 0:
            click.echo(f'{label} failed.', err=True)
            raise SystemExit(result.returncode)
    click.echo('\nAll tests passed.')


# -- prompt group --
@cli.group()
def prompt():
    """Prompt management commands."""
    pass


# Re-export the existing prompt manager CLI commands
# The pm group from utilities/prompt_manager/cli.py has: push, pull, list, diff
from utilities.prompt_manager.cli import pm as _pm_group
for cmd_name, cmd_obj in _pm_group.commands.items():
    prompt.add_command(cmd_obj, name=cmd_name)


# -- agent group --
@cli.group()
def agent():
    """Agent execution commands."""
    pass


@agent.command(name='run')
@click.argument('agent_name')
@click.option('--tenant-id', required=True, help='Tenant ID')
@click.option('--bu-id', required=True, help='Business Unit ID')
def agent_run(agent_name, tenant_id, bu_id):
    """Run a registered agent by name.

    Available agents are listed with `agent list`.
    """
    from dev_tools.run_agent import run_agent_by_name
    run_agent_by_name(agent_name, tenant_id, bu_id)


@agent.command(name='list')
def agent_list():
    """List all registered agents."""
    from dev_tools.run_agent import AGENT_REGISTRY
    if not AGENT_REGISTRY:
        click.echo('No agents registered.')
        return
    click.echo('Available agents:')
    for name, info in AGENT_REGISTRY.items():
        click.echo(f'  {name:<25} {info["description"]}')


# -- dev group --
@cli.group()
def dev():
    """Development server commands."""
    pass


@dev.command(name='start')
@click.option('--port', default=8000, help='Port number')
@click.option('--reload/--no-reload', default=True, help='Auto-reload on changes')
def dev_start(port, reload):
    """Start the development server with uvicorn."""
    import subprocess
    cmd = ['uvicorn', 'main:app', '--host', '0.0.0.0', '--port', str(port)]
    if reload:
        cmd.append('--reload')
    subprocess.run(cmd)


if __name__ == '__main__':
    cli()
```

### New file: `src/dev_tools/run_agent.py`

```python
"""Run a registered agent by name via CLI."""
import importlib
import click
from shared.infra.db.db_session_manager import db_session_manager, DbSessionType


# Registry: agent_name -> {class_path, description}
# Add new agents here as they are created
AGENT_REGISTRY = {
    'task-triage': {
        'class_path': 'project_mgmt.agents.task_triage.task_triage_agent.TaskTriageAgent',
        'description': 'Triage incoming tasks: set priority, assign labels',
    },
}


def run_agent_by_name(agent_name: str, tenant_id: str, bu_id: str):
    """Look up and execute a registered agent."""
    if agent_name not in AGENT_REGISTRY:
        click.echo(f"Unknown agent: {agent_name}")
        click.echo(f"Available agents: {', '.join(AGENT_REGISTRY.keys())}")
        raise SystemExit(1)

    entry = AGENT_REGISTRY[agent_name]
    module_path, class_name = entry['class_path'].rsplit('.', 1)
    module = importlib.import_module(module_path)
    agent_class = getattr(module, class_name)

    click.echo(f"Running agent: {agent_name} ({entry['description']})")
    with db_session_manager.get_session(DbSessionType.WRITE) as session:
        agent = agent_class(session=session, tenant_id=tenant_id, bu_id=bu_id)
        result = agent.run()
        click.echo(f"Agent completed: {result}")
```

### Update `pyproject.toml` entry point

```toml
[project.scripts]
rcv2 = "dev_tools.cli:cli"
```

This replaces the flat `dev = "dev_tools.cli:main_group"` and all individual linkedout agent entry points. Users run `rcv2 db reset`, `rcv2 test unit`, `rcv2 agent run task-triage --tenant-id ... --bu-id ...`, etc.

### Files to update for dev_tools cleanup

| File | Action |
|------|--------|
| `src/dev_tools/cli.py` | Rewrite (code above) |
| `src/dev_tools/run_agent.py` | Create (code above) |
| `src/dev_tools/db/reset_db.py` | No changes — `run_reset()` API is stable |
| `src/dev_tools/db/seed.py` | No changes — `main()` API is stable |
| `src/dev_tools/db/verify_seed.py` | Update entity imports (project_mgmt replaces rcm) |
| `src/dev_tools/db/validate_orm.py` | Update `ALL_ENTITIES` list (project_mgmt replaces rcm) |
| `src/dev_tools/db/fixed_data.py` | Update seed data (project_mgmt domain replaces rcm) |
| `src/dev_tools/run_all_agents.py` | Remove (linkedout-specific). Agent execution via `rcv2 agent run` |
| `pyproject.toml` | Update `[project.scripts]` (code above) |

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

### Overview

Three components: retry, timeout, and rate-limit. All config-driven via `BaseConfig`. Applied to the LLM client as the primary consumer. External API calls get the same decorators.

### New file: `src/shared/infra/reliability/__init__.py`
```python
from .retry_policy import retry_with_policy, RetryConfig, LLM_RETRY_CONFIG, EXTERNAL_API_RETRY_CONFIG
from .timeout_policy import timeout_with_policy, TimeoutConfig, LLM_TIMEOUT_CONFIG, EXTERNAL_API_TIMEOUT_CONFIG
from .rate_limiter import RateLimiter, RateLimitConfig

__all__ = [
    'retry_with_policy', 'RetryConfig', 'LLM_RETRY_CONFIG', 'EXTERNAL_API_RETRY_CONFIG',
    'timeout_with_policy', 'TimeoutConfig', 'LLM_TIMEOUT_CONFIG', 'EXTERNAL_API_TIMEOUT_CONFIG',
    'RateLimiter', 'RateLimitConfig',
]
```

### New file: `src/shared/infra/reliability/retry_policy.py`

```python
"""Config-driven retry policies using tenacity."""
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Tuple, Type

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

import logging

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    min_wait_seconds: float = 1.0
    max_wait_seconds: float = 60.0
    exponential_base: float = 2.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)


# Default configs for common use cases
LLM_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    min_wait_seconds=2.0,
    max_wait_seconds=30.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)

EXTERNAL_API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    min_wait_seconds=1.0,
    max_wait_seconds=15.0,
    retryable_exceptions=(ConnectionError, TimeoutError),
)


def retry_with_policy(config: RetryConfig | None = None):
    """Decorator factory for config-driven retries.

    Usage:
        @retry_with_policy(LLM_RETRY_CONFIG)
        def call_llm(prompt: str) -> str:
            ...

        @retry_with_policy()  # Uses default config
        def fetch_data() -> dict:
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @retry(
            stop=stop_after_attempt(config.max_attempts),
            wait=wait_exponential(
                multiplier=config.min_wait_seconds,
                max=config.max_wait_seconds,
                exp_base=config.exponential_base,
            ),
            retry=retry_if_exception_type(config.retryable_exceptions),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

### New file: `src/shared/infra/reliability/timeout_policy.py`

```python
"""Config-driven timeout policies."""
import signal
import threading
from dataclasses import dataclass
from functools import wraps
from typing import Callable


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""
    timeout_seconds: float = 30.0


# Default configs
LLM_TIMEOUT_CONFIG = TimeoutConfig(timeout_seconds=120.0)
EXTERNAL_API_TIMEOUT_CONFIG = TimeoutConfig(timeout_seconds=30.0)


class OperationTimeoutError(Exception):
    """Raised when an operation exceeds its timeout."""
    pass


def timeout_with_policy(config: TimeoutConfig | None = None):
    """Decorator factory for config-driven timeouts.

    Usage:
        @timeout_with_policy(LLM_TIMEOUT_CONFIG)
        def call_llm(prompt: str) -> str:
            ...

    Note: Uses signal-based timeout on Unix main thread.
    Falls back to no timeout enforcement on non-Unix or non-main-thread
    (the underlying call may still have its own socket/HTTP timeout).
    """
    if config is None:
        config = TimeoutConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # signal.alarm only works on Unix main thread
            if threading.current_thread() is not threading.main_thread():
                return func(*args, **kwargs)

            def handler(signum, frame):
                raise OperationTimeoutError(
                    f"{func.__name__} exceeded timeout of {config.timeout_seconds}s"
                )

            old_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(int(config.timeout_seconds))
            try:
                return func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        return wrapper
    return decorator
```

### New file: `src/shared/infra/reliability/rate_limiter.py`

```python
"""Simple token-bucket rate limiter for outbound API calls."""
import time
import threading
from dataclasses import dataclass
from functools import wraps
from typing import Callable

import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting.

    Uses a token-bucket approach: `max_calls` allowed per `period_seconds`.
    """
    max_calls: int = 60
    period_seconds: float = 60.0


class RateLimiter:
    """Thread-safe token-bucket rate limiter.

    Usage as a context-managed guard:
        limiter = RateLimiter(RateLimitConfig(max_calls=60, period_seconds=60))

        def call_llm():
            limiter.acquire()   # blocks until a slot is available
            return do_llm_call()

    Usage as a decorator:
        @RateLimiter(RateLimitConfig(max_calls=10, period_seconds=60)).decorator
        def call_api():
            ...
    """

    def __init__(self, config: RateLimitConfig):
        self._config = config
        self._lock = threading.Lock()
        self._call_times: list[float] = []

    def acquire(self) -> None:
        """Block until a rate-limit slot is available."""
        while True:
            with self._lock:
                now = time.monotonic()
                # Remove calls outside the window
                cutoff = now - self._config.period_seconds
                self._call_times = [t for t in self._call_times if t > cutoff]

                if len(self._call_times) < self._config.max_calls:
                    self._call_times.append(now)
                    return

                # Calculate wait time until oldest call falls out of window
                wait = self._call_times[0] + self._config.period_seconds - now

            logger.debug(
                'Rate limit reached (%d/%d in %.0fs window), waiting %.1fs',
                len(self._call_times), self._config.max_calls,
                self._config.period_seconds, wait,
            )
            time.sleep(max(wait, 0.1))

    @property
    def decorator(self):
        """Return a decorator that applies this rate limiter."""
        limiter = self

        def _decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                limiter.acquire()
                return func(*args, **kwargs)
            return wrapper
        return _decorator
```

### Wiring reliability into the LLM client

The existing `LLMClient` at `src/utilities/llm_manager/llm_client.py` has `call_llm()` and `call_llm_structured()` abstract methods, with `LangchainLLMClient` as the concrete implementation (in `llm_factory.py`).

**File to modify**: `src/utilities/llm_manager/llm_factory.py`

The factory creates `LangchainLLMClient` instances. We apply reliability at the factory level so all LLM calls automatically get retry + timeout + rate-limit:

```python
# In LangchainLLMClient or the factory wrapper:

from shared.infra.reliability import (
    retry_with_policy, RetryConfig,
    timeout_with_policy, TimeoutConfig,
    RateLimiter, RateLimitConfig,
)
from shared.config.config import backend_config

# Build configs from settings
_llm_retry = RetryConfig(
    max_attempts=backend_config.LLM_RETRY_MAX_ATTEMPTS,
    min_wait_seconds=backend_config.LLM_RETRY_MIN_WAIT,
    max_wait_seconds=backend_config.LLM_RETRY_MAX_WAIT,
    retryable_exceptions=(ConnectionError, TimeoutError, Exception),
    # Note: narrow the exception types to actual transient errors from the provider
)

_llm_timeout = TimeoutConfig(
    timeout_seconds=backend_config.LLM_TIMEOUT_SECONDS,
)

_llm_rate_limiter = RateLimiter(RateLimitConfig(
    max_calls=backend_config.RATE_LIMIT_LLM_RPM,
    period_seconds=60.0,
))
```

**Where to apply**: In the concrete `LangchainLLMClient.call_llm()` and `call_llm_structured()` implementations. The pattern is:

```python
class LangchainLLMClient(LLMClient):

    @retry_with_policy(_llm_retry)
    @timeout_with_policy(_llm_timeout)
    def call_llm(self, message: LLMMessage) -> str:
        _llm_rate_limiter.acquire()
        # ... existing langchain invoke logic ...

    @retry_with_policy(_llm_retry)
    @timeout_with_policy(_llm_timeout)
    def call_llm_structured(self, message: LLMMessage, output_schema) -> Any:
        _llm_rate_limiter.acquire()
        # ... existing langchain structured invoke logic ...
```

This ensures:
1. Rate limiter checks before each call
2. Timeout wraps the entire call (including any provider-side wait)
3. Retries wrap the timeout (so a timeout triggers a retry, not a permanent failure)

### Config fields to add to `BaseConfig`

```python
# Reliability
LLM_RETRY_MAX_ATTEMPTS: int = 3
LLM_RETRY_MIN_WAIT: float = 2.0
LLM_RETRY_MAX_WAIT: float = 30.0
LLM_TIMEOUT_SECONDS: float = 120.0
EXTERNAL_API_RETRY_MAX_ATTEMPTS: int = 3
EXTERNAL_API_TIMEOUT_SECONDS: float = 30.0
RATE_LIMIT_LLM_RPM: int = 60
RATE_LIMIT_LLM_TPM: int = 100000
```

### Verify
```bash
# Unit test: retry decorator
python -c "
from shared.infra.reliability import retry_with_policy, RetryConfig

call_count = 0

@retry_with_policy(RetryConfig(max_attempts=3, retryable_exceptions=(ValueError,)))
def flaky():
    global call_count
    call_count += 1
    if call_count < 3:
        raise ValueError('transient')
    return 'ok'

assert flaky() == 'ok'
assert call_count == 3
print('Retry test passed')
"

# Unit test: rate limiter
python -c "
import time
from shared.infra.reliability import RateLimiter, RateLimitConfig

rl = RateLimiter(RateLimitConfig(max_calls=3, period_seconds=1.0))
start = time.monotonic()
for _ in range(4):
    rl.acquire()
elapsed = time.monotonic() - start
assert elapsed >= 0.9, f'Expected >= 1s delay, got {elapsed:.2f}s'
print(f'Rate limiter test passed ({elapsed:.2f}s for 4 calls with limit 3/1s)')
"
```

---

## Step 3: Structured Logging

### Overview

Replace the basic `logging.basicConfig` in `src/shared/utilities/logger.py` with environment-aware structured logging. Add HTTP request/response middleware. Add agent execution logging that integrates with the agent lifecycle from Phase 6.

### New file: `src/shared/infra/logging/__init__.py`
```python
from .setup import setup_logging

__all__ = ['setup_logging']
```

### New file: `src/shared/infra/logging/setup.py`

```python
"""Structured logging configuration."""
import logging
import json
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """JSON log formatter for production.

    Produces one JSON object per log line. Includes extra fields
    (request_id, agent_name, run_id, tenant_id, bu_id) when present
    on the LogRecord.
    """

    EXTRA_FIELDS = ('request_id', 'agent_name', 'run_id', 'tenant_id', 'bu_id')

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry['exception'] = self.formatException(record.exc_info)
        for key in self.EXTRA_FIELDS:
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val
        return json.dumps(log_entry)


class ReadableFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'

    def __init__(self):
        super().__init__(self.FORMAT, datefmt='%H:%M:%S')


def setup_logging(environment: str = 'local', log_level: str = 'INFO'):
    """Configure logging based on environment.

    Call this once at application startup (in main.py lifespan).

    Args:
        environment: 'local', 'dev', 'test', or 'prod'
        log_level: Python log level string
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)

    if environment == 'prod':
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(ReadableFormatter())

    root.addHandler(handler)

    # Quiet noisy libraries
    for lib in ('sqlalchemy.engine', 'httpcore', 'httpx', 'urllib3', 'langchain'):
        logging.getLogger(lib).setLevel(logging.WARNING)
```

### New file: `src/shared/infra/logging/request_middleware.py`

```python
"""FastAPI request/response logging middleware."""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger('http')


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log HTTP request/response pairs with timing and request ID.

    Adds X-Request-ID header to responses for tracing.
    Skips /health and /docs endpoints to reduce noise.
    """

    SKIP_PATHS = {'/health', '/docs', '/openapi.json', '/favicon.ico'}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        logger.info(
            '%s %s [%s]',
            request.method,
            request.url.path,
            request_id,
            extra={'request_id': request_id},
        )

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            '%s %s [%s] %d %.0fms',
            request.method,
            request.url.path,
            request_id,
            response.status_code,
            duration_ms,
            extra={'request_id': request_id},
        )

        response.headers['X-Request-ID'] = request_id
        return response
```

### New file: `src/shared/infra/logging/agent_logger.py`

```python
"""Agent execution logging — integrates with agent lifecycle (Phase 6).

Provides structured logging for agent runs: start, LLM call, validation,
enrichment, completion/failure. Each log entry includes agent_name and run_id
so logs can be correlated with AgentRun records in the database.

Usage in an agent:
    from shared.infra.logging.agent_logger import AgentLogger

    class TaskTriageAgent:
        def __init__(self, ...):
            self._log = AgentLogger(agent_name='task-triage')

        def run(self, run_id: str, ...):
            self._log.start(run_id, tenant_id=..., bu_id=..., input_params={...})

            context = self._build_context()
            self._log.context_built(run_id, context_summary='...')

            llm_response = self._call_llm(context)
            self._log.llm_call_completed(run_id, model='gpt-4o', latency_ms=1200, tokens=350)

            validated = self._validate(llm_response)
            self._log.validation_completed(run_id, valid=True)

            enriched = self._enrich(validated)
            self._log.enrichment_completed(run_id)

            self._persist(enriched)
            self._log.completed(run_id, summary='...')

            # On failure:
            self._log.failed(run_id, error='...')
"""
import logging
from typing import Any


class AgentLogger:
    """Structured logger for agent execution lifecycle."""

    def __init__(self, agent_name: str):
        self._agent_name = agent_name
        self._logger = logging.getLogger(f'agent.{agent_name}')

    def _extra(self, run_id: str, **kwargs) -> dict:
        base = {'agent_name': self._agent_name, 'run_id': run_id}
        base.update(kwargs)
        return base

    def start(self, run_id: str, tenant_id: str, bu_id: str, input_params: dict | None = None):
        self._logger.info(
            'Agent started | tenant=%s bu=%s params=%s',
            tenant_id, bu_id, input_params,
            extra=self._extra(run_id, tenant_id=tenant_id, bu_id=bu_id),
        )

    def context_built(self, run_id: str, context_summary: str = ''):
        self._logger.info(
            'Context built | %s', context_summary,
            extra=self._extra(run_id),
        )

    def llm_call_completed(self, run_id: str, model: str = '', latency_ms: float = 0, tokens: int = 0):
        self._logger.info(
            'LLM call completed | model=%s latency=%.0fms tokens=%d',
            model, latency_ms, tokens,
            extra=self._extra(run_id),
        )

    def validation_completed(self, run_id: str, valid: bool = True, errors: list[str] | None = None):
        if valid:
            self._logger.info('Validation passed', extra=self._extra(run_id))
        else:
            self._logger.warning(
                'Validation failed | errors=%s', errors,
                extra=self._extra(run_id),
            )

    def enrichment_completed(self, run_id: str):
        self._logger.info('Enrichment completed', extra=self._extra(run_id))

    def completed(self, run_id: str, summary: str = ''):
        self._logger.info(
            'Agent completed | %s', summary,
            extra=self._extra(run_id),
        )

    def failed(self, run_id: str, error: str = ''):
        self._logger.error(
            'Agent failed | %s', error,
            extra=self._extra(run_id),
        )
```

### How agent logging integrates with Phase 6 agent lifecycle

The agent lifecycle from Phase 6 follows: context build -> LLM call -> validation -> enrichment -> persistence. `AgentLogger` mirrors this lifecycle with one method per stage. The integration point:

1. **Base agent class** (e.g., `BaseAgent` from Phase 6) instantiates `AgentLogger` in `__init__`
2. Each lifecycle method calls the corresponding `AgentLogger` method
3. The `run_id` from `AgentRunEntity` is passed through, so log entries correlate with DB records
4. In prod (JSON formatter), these logs become searchable by `agent_name` and `run_id`

**No changes to Phase 6 agent architecture** — `AgentLogger` is a logging helper, not a lifecycle change. Agents that don't use it still work fine.

### Wire into `main.py`

```python
# At top of lifespan or before app creation:
from shared.infra.logging.setup import setup_logging
from shared.infra.logging.request_middleware import RequestLoggingMiddleware

# In lifespan startup:
setup_logging(
    environment=backend_config.ENVIRONMENT,
    log_level=backend_config.LOG_LEVEL,
)

# After app creation:
app.add_middleware(RequestLoggingMiddleware)
```

### Update `src/shared/utilities/logger.py`

Keep `get_logger()` and `set_level()` as convenience wrappers (existing code uses them everywhere). But delegate actual setup to `setup_logging()`:

```python
"""Logging utilities — thin wrappers around stdlib logging.

Actual logging configuration (formatters, handlers) is in
shared.infra.logging.setup.setup_logging() and is called once
at app startup in main.py.
"""
import logging


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


def set_level(level: str) -> None:
    """Set the root logging level."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_level)
```

Remove the `logging.basicConfig(...)` call that currently runs at import time — it conflicts with `setup_logging()`.

### Verify
```bash
# Start server locally, make a request, check readable format
ENVIRONMENT=local python main.py &
sleep 2
curl http://localhost:8000/health
# Expect: "HH:MM:SS | INFO     | http | GET /health [abc12345] 200 5ms"
kill %1

# Check JSON format for prod
ENVIRONMENT=prod python -c "
from shared.infra.logging.setup import setup_logging
setup_logging('prod', 'INFO')
import logging
logging.getLogger('test').info('hello', extra={'agent_name': 'task-triage', 'run_id': 'run-001'})
"
# Expect: {"timestamp":"...","level":"INFO","logger":"test","message":"hello","agent_name":"task-triage","run_id":"run-001"}
```

---

## Step 4: Config Cleanup

### File: `src/shared/config/config.py` (modify)

Add missing config fields. Keep the flat `BaseConfig` pattern — no class hierarchy. The env-file-per-environment approach is cleaner.

```python
class BaseConfig(BaseSettings):
    # ... existing fields unchanged ...

    # Auth (added in Phase 4, declared here for completeness)
    AUTH_ENABLED: bool = True
    FIREBASE_ENABLED: bool = True
    FIREBASE_PROJECT_ID: str = ''
    FIREBASE_CREDENTIALS_PATH: str = ''

    # LLM Tracing (added in Phase 6, declared here)
    LLM_TRACING_ENABLED: bool = False

    # Reliability (new in Phase 7)
    LLM_RETRY_MAX_ATTEMPTS: int = 3
    LLM_RETRY_MIN_WAIT: float = 2.0
    LLM_RETRY_MAX_WAIT: float = 30.0
    LLM_TIMEOUT_SECONDS: float = 120.0
    EXTERNAL_API_RETRY_MAX_ATTEMPTS: int = 3
    EXTERNAL_API_TIMEOUT_SECONDS: float = 30.0
    RATE_LIMIT_LLM_RPM: int = 60
    RATE_LIMIT_LLM_TPM: int = 100000
```

### File: `.env.local` (update)

```env
# Local Development Configuration
ENVIRONMENT=local
DATABASE_URL=postgresql://postgres:localdbpassword@localhost:5432/sample_backend_dev
LOG_LEVEL=DEBUG
DEBUG=true
DB_ECHO_LOG=false

# Auth — disabled for local dev
AUTH_ENABLED=false
FIREBASE_ENABLED=false

# LLM
LLM_PROVIDER=azure_openai
LLM_MODEL=gpt-4o
LLM_API_KEY=<your-key>
LLM_API_BASE=<your-azure-endpoint>
LLM_API_VERSION=2025-01-01-preview
PROMPT_FROM_LOCAL_FILE=true
LLM_TRACING_ENABLED=false

# Langfuse (optional for local)
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=
```

### File: `.env.test` (update)

```env
# Test Environment Configuration
ENVIRONMENT=test
DATABASE_URL=sqlite:///:memory:
LOG_LEVEL=WARNING
DEBUG=false
DB_ECHO_LOG=false

# Auth — disabled for tests
AUTH_ENABLED=false

# LLM — local prompts, no tracing
PROMPT_FROM_LOCAL_FILE=true
LLM_TRACING_ENABLED=false
LLM_PROVIDER=azure_openai
LLM_MODEL=gpt-4o
```

### File: `.env.prod` (template — not committed with real values)

```env
# Production Environment Configuration
# Copy to .env.prod and fill in real values
# NEVER commit the real .env.prod with actual secrets
ENVIRONMENT=prod
DATABASE_URL=postgresql://user:pass@host:5432/dbname
LOG_LEVEL=INFO
DEBUG=false

# Auth
AUTH_ENABLED=true
FIREBASE_ENABLED=true
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_CREDENTIALS_PATH=/path/to/credentials.json

# LLM
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=your-key
PROMPT_FROM_LOCAL_FILE=false
LLM_TRACING_ENABLED=true

# Langfuse
LANGFUSE_PUBLIC_KEY=your-key
LANGFUSE_SECRET_KEY=your-key
LANGFUSE_HOST=https://cloud.langfuse.com

# Reliability
LLM_RETRY_MAX_ATTEMPTS=3
LLM_TIMEOUT_SECONDS=120
RATE_LIMIT_LLM_RPM=60
```

### File: `.gitignore` (verify these are present)

```
.env
.env.local
.env.prod
# .env.test is committed (no secrets, needed for CI)
```

### Verify
```bash
ENVIRONMENT=local python -c "from shared.config.config import backend_config; print(f'AUTH={backend_config.AUTH_ENABLED} TRACE={backend_config.LLM_TRACING_ENABLED}')"
# Expect: AUTH=False TRACE=False

ENVIRONMENT=test python -c "from shared.config.config import backend_config; print(f'AUTH={backend_config.AUTH_ENABLED}')"
# Expect: AUTH=False
```

---

## Step 5: Alembic Migration Cleanup

### File: `migrations/env.py` (modify)

Replace all 24 rcm entity imports with project_mgmt domain entities:

```python
# Organization entities
from organization.entities.tenant_entity import TenantEntity  # noqa: F401
from organization.entities.bu_entity import BuEntity  # noqa: F401

# Project management domain entities
from project_mgmt.label.entities.label_entity import LabelEntity  # noqa: F401
from project_mgmt.priority.entities.priority_entity import PriorityEntity  # noqa: F401
from project_mgmt.project.entities.project_entity import ProjectEntity  # noqa: F401
from project_mgmt.task.entities.task_entity import TaskEntity  # noqa: F401

# Agent infrastructure entities
from project_mgmt.agents.entities.agent_run_entity import AgentRunEntity  # noqa: F401
```

Note: Exact entity paths depend on Phase 3 and Phase 6 output. The imports above are placeholders based on the high-level plan's module naming convention.

### Generate fresh migration

```bash
# Remove old rcm migrations (all linkedout-era)
rm -f migrations/versions/*.py
rm -f migrations/versions/__pycache__/*.pyc

# Generate fresh initial migration for the new domain
alembic revision --autogenerate -m "initial_schema"

# Verify upgrade works
alembic upgrade head

# Verify downgrade works
alembic downgrade base

# Verify re-upgrade works
alembic upgrade head

# Verify no pending changes
alembic check
```

### File: `src/shared/infra/db/db_session_manager.py` (modify)

Update the entity package imports that register entities with SQLAlchemy:

```python
# Replace:
import organization.entities  # noqa
import rcm.common.entities  # noqa
import rcm.inventory.entities  # noqa
import rcm.planner.entities  # noqa
import rcm.demand.entities  # noqa
import rcm.resources.entities  # noqa

# With:
import organization.entities  # noqa
import project_mgmt.label.entities  # noqa
import project_mgmt.priority.entities  # noqa
import project_mgmt.project.entities  # noqa
import project_mgmt.task.entities  # noqa
import project_mgmt.agents.entities  # noqa
```

### File: `src/dev_tools/db/validate_orm.py` (modify)

Update `ALL_ENTITIES` list and entity imports to reference the new project_mgmt domain entities instead of rcm entities.

### File: `src/dev_tools/db/verify_seed.py` (modify)

Update entity imports and `counts` dict to reference project_mgmt entities.

### Verify
```bash
alembic check  # Should show "No new upgrade operations detected"
python -m dev_tools.cli db validate-orm  # All checks pass
```

---

## Step 6: Update `main.py`

### Router registration (modify)

Replace all rcm router imports with project_mgmt:

```python
# Organization routers (unchanged)
from organization.controllers.tenant_controller import tenants_router
from organization.controllers.bu_controller import bus_router

# Project management routers
from project_mgmt.label.controllers.label_controller import label_router
from project_mgmt.priority.controllers.priority_controller import priority_router
from project_mgmt.project.controllers.project_controller import project_router
from project_mgmt.task.controllers.task_controller import task_router

# Agent infrastructure routers
from project_mgmt.agents.controllers.agent_run_controller import agent_run_router

# Register all
app.include_router(tenants_router)
app.include_router(bus_router)
app.include_router(label_router)
app.include_router(priority_router)
app.include_router(project_router)
app.include_router(task_router)
app.include_router(agent_run_router)
```

### Wire logging and middleware

```python
from shared.infra.logging.setup import setup_logging
from shared.infra.logging.request_middleware import RequestLoggingMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging(
        environment=backend_config.ENVIRONMENT,
        log_level=backend_config.LOG_LEVEL,
    )
    logger.info('Starting Reference Code V2 API...')
    yield
    logger.info('Shutting down...')

# After app creation
app.add_middleware(RequestLoggingMiddleware)
# CORSMiddleware must come after RequestLoggingMiddleware (order matters — Starlette processes in reverse)
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
```

### Update app metadata

```python
app = FastAPI(
    title='Reference Code V2 API',
    description='FastAPI reference implementation with MVCS architecture, multi-tenancy, and AI agent support.',
    version='1.0.0',
    lifespan=lifespan,
)
```

---

## Step 7: Update `setup.sh`

Minor updates:
- Change "Sample Backend" references to "Reference Code V2"
- Default env file created is `.env.local` (already the case)
- Add `tenacity` to dependency check

### Update `requirements.txt`

Ensure these are present:

```
tenacity>=8.0
```

(Already has: click, langfuse, langchain-openai, pydantic-settings, alembic, etc.)

---

## Step 8: Update `pyproject.toml`

```toml
[project]
name = "reference-code-v2"
version = "1.0.0"

[project.scripts]
rcv2 = "dev_tools.cli:cli"
```

Remove all linkedout-specific entry points (individual agent commands, `run-all-agents`, `visualizer`, `fe-setup`).

---

## Step 9: Final Verification

```bash
# 1. CLI smoke test
rcv2 --help
rcv2 db --help
rcv2 test --help
rcv2 prompt --help
rcv2 agent --help
rcv2 agent list
rcv2 dev --help

# 2. Config loads for all environments
ENVIRONMENT=local python -c "from shared.config.config import backend_config; print(f'env={backend_config.ENVIRONMENT} auth={backend_config.AUTH_ENABLED} trace={backend_config.LLM_TRACING_ENABLED}')"
ENVIRONMENT=test python -c "from shared.config.config import backend_config; print(f'env={backend_config.ENVIRONMENT} auth={backend_config.AUTH_ENABLED}')"

# 3. Structured logging
ENVIRONMENT=local python -c "
from shared.infra.logging.setup import setup_logging
setup_logging('local', 'INFO')
import logging; logging.getLogger('test').info('readable format check')
"
ENVIRONMENT=prod python -c "
from shared.infra.logging.setup import setup_logging
setup_logging('prod', 'INFO')
import logging; logging.getLogger('test').info('json format check')
"

# 4. Agent logging
python -c "
from shared.infra.logging.setup import setup_logging
setup_logging('local', 'INFO')
from shared.infra.logging.agent_logger import AgentLogger
log = AgentLogger('task-triage')
log.start('run-001', 'tenant-1', 'bu-1', {'task_id': 'task-123'})
log.llm_call_completed('run-001', model='gpt-4o', latency_ms=1200, tokens=350)
log.completed('run-001', summary='triaged 1 task')
"

# 5. Reliability
python -c "
from shared.infra.reliability import retry_with_policy, RetryConfig, RateLimiter, RateLimitConfig
print('Reliability imports OK')
"

# 6. Alembic
alembic upgrade head
alembic downgrade base
alembic upgrade head
alembic check

# 7. ORM validation
rcv2 db validate-orm

# 8. Full test suite
rcv2 test all

# 9. Dev server starts
rcv2 dev start &
sleep 3
curl -s http://localhost:8000/health | python -m json.tool
kill %1
```

---

## Execution Order Summary

| Order | Step | Files Modified | Files Created | Risk | Notes |
|-------|------|---------------|---------------|------|-------|
| 1 | Restructure CLI | `cli.py`, `pyproject.toml` | `run_agent.py` | Low | Core CLI restructure |
| 2 | Reliability infra | `llm_factory.py` | `reliability/__init__.py`, `retry_policy.py`, `timeout_policy.py`, `rate_limiter.py` | Low | New module, no existing code broken |
| 3 | Structured logging | `logger.py`, `main.py` | `logging/__init__.py`, `setup.py`, `request_middleware.py`, `agent_logger.py` | Low | Replaces basicConfig |
| 4 | Config cleanup | `config.py` | `.env.local`, `.env.test`, `.env.prod` (update) | Low | Additive field additions |
| 5 | Alembic migrations | `env.py`, `db_session_manager.py`, `validate_orm.py`, `verify_seed.py` | `migrations/versions/initial_schema.py` | Medium | Entity import swap |
| 6 | Update main.py | `main.py` | — | Medium | Router swap + middleware wiring |
| 7 | Update setup.sh | `setup.sh`, `requirements.txt` | — | Low | Text/dep updates |
| 8 | Update pyproject.toml | `pyproject.toml` | — | Low | Entry point cleanup |
| 9 | Final verification | — | — | — | All smoke tests |

---

## File Inventory

### New files (10)
| File | Purpose |
|------|---------|
| `src/shared/infra/reliability/__init__.py` | Reliability module exports |
| `src/shared/infra/reliability/retry_policy.py` | Tenacity-based retry decorator factory |
| `src/shared/infra/reliability/timeout_policy.py` | Signal-based timeout decorator factory |
| `src/shared/infra/reliability/rate_limiter.py` | Token-bucket rate limiter |
| `src/shared/infra/logging/__init__.py` | Logging module exports |
| `src/shared/infra/logging/setup.py` | Environment-aware logging setup (JSON/readable) |
| `src/shared/infra/logging/request_middleware.py` | FastAPI HTTP request/response logging |
| `src/shared/infra/logging/agent_logger.py` | Agent lifecycle structured logging |
| `src/dev_tools/run_agent.py` | Agent registry and CLI runner |
| `migrations/versions/<hash>_initial_schema.py` | Fresh migration for project_mgmt entities |

### Modified files (9)
| File | Changes |
|------|---------|
| `src/dev_tools/cli.py` | Rewrite: Click groups (db, test, prompt, agent, dev) |
| `src/shared/config/config.py` | Add AUTH, LLM_TRACING, reliability, rate-limit config fields |
| `src/shared/utilities/logger.py` | Remove basicConfig, keep get_logger/set_level |
| `src/utilities/llm_manager/llm_factory.py` | Apply retry/timeout/rate-limit decorators |
| `main.py` | Replace rcm routers, add logging/middleware |
| `migrations/env.py` | Replace rcm entity imports with project_mgmt |
| `src/shared/infra/db/db_session_manager.py` | Replace rcm entity package imports |
| `src/dev_tools/db/validate_orm.py` | Update ALL_ENTITIES list |
| `src/dev_tools/db/verify_seed.py` | Update entity imports and counts |
| `pyproject.toml` | Rename project, update entry points |
| `setup.sh` | Update title references |
| `requirements.txt` | Add `tenacity>=8.0` |
| `.env.local`, `.env.test`, `.env.prod` | Update with new config vars |

### Deleted files
| File | Reason |
|------|--------|
| `src/dev_tools/run_all_agents.py` | Terrantic-specific, replaced by `rcv2 agent run` |
| `migrations/versions/*.py` (old) | Replaced by fresh initial migration |
| `src/dev_tools/planner_agent_iterations/` | Terrantic-specific eval tooling (if not already removed in Phase 3) |

---

## What This Phase Does NOT Do (Deferred)

| Deferred | Reason |
|----------|--------|
| Advanced log aggregation (ELK, Datadog) | Out of scope for reference repo |
| CI/CD pipeline | Not part of template requirements |
| Docker/compose files | Can be added later as needed |
| Token-level rate limiting enforcement | RPM-level is sufficient for v1; TPM tracking would require hooking into LLM response metadata |
| Health check DB connectivity | Simple `/health` is sufficient; deep health checks add complexity |

---

## Total Estimated Changes

| Type | Count |
|------|-------|
| Files created | 10 |
| Files modified | ~13 |
| Files deleted | Old migrations + linkedout-specific dev_tools |

**This phase is polish and operational completeness.** All the hard architectural work is done in Phases 2-6. Phase 7 makes the repo feel finished and usable — a developer cloning the repo can run `rcv2 --help` and immediately know what's available.

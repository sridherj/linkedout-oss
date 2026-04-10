# Phase 02: Environment & Configuration System — Shared Context

**Project:** LinkedOut OSS
**Phase:** 2 of 13
**Phase plan:** `docs/plan/phase-02-env-config.md`
**Status:** Ready for execution

---

## What This Phase Delivers

Replace the current env-file-based config system with a three-layer config hierarchy:

```
Environment variables  >  config.yaml  >  secrets.yaml  >  Code defaults
```

All config, data, and logs consolidate under `~/linkedout-data/`. Clean break from old env-file pattern — no backward compatibility.

---

## Key Decision Docs

| Doc | Path | Key Takeaway |
|-----|------|-------------|
| Config hierarchy & layout | `docs/decision/env-config-design.md` | Three-layer: env > config.yaml > secrets.yaml > defaults. `LINKEDOUT_` prefix. Industry-standard names kept (`DATABASE_URL`, `OPENAI_API_KEY`). |
| Data directory convention | `docs/decision/2026-04-07-data-directory-convention.md` | Default `~/linkedout-data/`, override via `LINKEDOUT_DATA_DIR` |
| CLI surface | `docs/decision/cli-surface.md` | `linkedout config show` and `linkedout config path` — Phase 6 work, not Phase 2 |
| Logging strategy | `docs/decision/logging-observability-strategy.md` | Keep loguru. Config vars defined in Phase 2, logging implementation in Phase 3. |
| Queue removal | `docs/decision/queue-strategy.md` | Procrastinate removed — no queue config vars needed |
| Embedding model | `docs/decision/2026-04-07-embedding-model-selection.md` | nomic-embed-text-v1.5 default local, OpenAI optional |

---

## Architecture Decisions (Binding)

1. **Unified directory:** All config, data, logs under `~/linkedout-data/`. No separate `~/.linkedout/`.
2. **DB password in config.yaml, NOT secrets.yaml:** Single-user localhost — password is not a real security boundary.
3. **No backward compat:** Clean break. No deprecated env var mappings.
4. **`LINKEDOUT_` prefix** for custom vars. Industry-standard names (`DATABASE_URL`, `OPENAI_API_KEY`, `LANGFUSE_*`) keep their standard names.
5. **Flatten `LLMConfig`/`ReliabilityConfig`:** Flatten into `LinkedOutSettings` — pydantic-settings handles flat env vars better.
6. **Extension config caching:** Load config once at startup, cache in module-level variable. Not per-call async.
7. **CORS default:** Keep `['*']` for now — tightening is Phase 6.
8. **pydantic-settings v2 API:** Verify version with `pip show pydantic-settings` and use correct `settings_customise_sources` API.

---

## Naming Conventions

- **Python modules:** `snake_case` — `settings.py`, `yaml_sources.py`, `agent_context.py`
- **Config field names:** `snake_case` — `embedding_provider`, `backend_port`
- **Env vars:** `LINKEDOUT_` prefix + `UPPER_SNAKE_CASE` — `LINKEDOUT_EMBEDDING_PROVIDER`
- **Industry-standard vars:** No prefix — `DATABASE_URL`, `OPENAI_API_KEY`, `APIFY_API_KEY`, `LANGFUSE_*`
- **YAML keys:** `snake_case` matching the pydantic field names
- **TypeScript:** `camelCase` for config fields — `backendUrl`, `stalenessDays`

---

## Key File Paths

### Current state (what exists):
- `backend/src/shared/config/config.py` — current `AppConfig(BaseSettings)` with `LLMConfig` + `ReliabilityConfig`
- `backend/src/shared/config/__init__.py` — exports current config
- `backend/main.py` — current startup with `dotenv.load_dotenv(_get_env_file())`
- `extension/lib/constants.ts` — all hardcoded values
- `backend/conftest.py` — test config setup (682 lines)
- `backend/requirements.txt` — needs `PyYAML>=6.0` added

### To create:
- `backend/.env.example` — env vars reference
- `backend/src/shared/config/settings.py` — new `LinkedOutSettings` class
- `backend/src/shared/config/yaml_sources.py` — YAML custom sources
- `backend/src/shared/config/agent_context.py` — agent context file generator
- `extension/lib/config.ts` — runtime config module

### To modify:
- `backend/src/shared/config/__init__.py` — export new settings
- `backend/src/shared/config/config.py` — facade delegating to new settings
- `backend/main.py` — remove old env file loading
- `extension/lib/constants.ts` — split configurable vs truly-constant values
- `extension/wxt.config.ts` — add `VITE_BACKEND_URL` support
- All backend files with `os.getenv()` / `backend_config.X` calls

---

## Current Config System (What to Replace)

```python
# backend/src/shared/config/config.py (current)
class AppConfig(BaseSettings):
    # Composed from LLMConfig + ReliabilityConfig
    # Loads from .env.local / .env.test / .env.prod based on ENVIRONMENT var
    # Global: backend_config = get_config()
```

```python
# backend/main.py (current)
dotenv.load_dotenv(_get_env_file())  # selects file by ENVIRONMENT var
```

---

## Dependencies Between Sub-Phases

```
SP1 (.env.example) ─────────────── independent
SP2 (config module + dirs + secrets) ─┬─ SP3 (agent context + validation)
                                      ├─ SP4 (main.py refactor)
                                      ├─ SP5 (update all consumers)
                                      └─ SP7 (test infrastructure)
SP6 (extension config) ─────────────── independent (parallel with SP4/SP5)
SP7 (tests) ─────────────────────────── depends on SP2-SP6
```

---

## Complete Environment Variable Table

See `docs/decision/env-config-design.md` section "Complete Environment Variable Table" for the authoritative list. Groups: Core, Server, Embeddings, LLM, API Keys, Logging & Observability, Langfuse, Extension Runtime, Extension Build-Time.

---

## What This Phase Does NOT Do

- `/linkedout-setup` skill (Phase 9)
- Logging infrastructure changes (Phase 3) — but config vars for logging are defined here
- Constants extraction (Phase 4) — scoring weights, thresholds stay hardcoded
- Embedding provider abstraction (Phase 5) — but config vars for providers are defined here
- CLI commands `linkedout config show/path` (Phase 6)
- Extension options page (Phase 12)
- Procrastinate removal (Phase 6 — but no Procrastinate config vars are added)
- Firebase removal (Phase 6 — but Firebase config vars are not added to `LinkedOutSettings`)

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing any Python code — naming, formatting, type hints |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing tests (SP: 2J) — naming conventions, AAA pattern, fixtures |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating new modules (`config.py`, `yaml_sources.py`, `agent_context.py`) |
| `.claude/skills/mvcs-compliance/SKILL.md` | When modifying service/config layers — layer responsibility rules |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/integration-test-creator-agent.md` | 2J (Tests) | Reference for test fixture patterns, seeded data setup, integration test conventions |

### Notes
- Phase 2 is primarily config infrastructure, so CRUD agents don't apply
- The `integration-test-creator-agent` provides patterns for DB-backed test fixtures that apply to config integration tests

# Phase 2: Environment & Configuration System — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Phase:** 2 of 13
**Status:** Ready for implementation
**Depends on:** Phase 1 (OSS Repository Scaffolding) — repo structure, .gitignore, CI
**Consumed by:** Every subsequent phase — this is the config foundation

---

## Phase Overview

**Goal:** Replace the current environment-file-based config system (`ENVIRONMENT` → `.env.local/.env.test/.env.prod`, scattered `os.getenv()` calls, Pydantic `BaseSettings` with per-env file selection) with the three-layer config hierarchy approved in Spike 0G:

```
Environment variables  >  config.yaml  >  secrets.yaml  >  Code defaults
```

All config, data, and logs consolidate under `~/linkedout-data/` (per `docs/decision/env-config-design.md` and `docs/decision/2026-04-07-data-directory-convention.md`). No backward compatibility with the old env-file pattern — this is a clean break (approved by SJ).

**What this phase delivers:**
1. A new `LinkedOutSettings` pydantic-settings class with YAML custom sources
2. `.env.example` in the repo root for reference
3. `~/linkedout-data/` directory structure creation on startup
4. Extension config refactor (`lib/constants.ts` → `lib/config.ts` with storage API)
5. All existing code updated to use the new config module
6. Backend boots cleanly with either env vars alone, config.yaml alone, or a combination

**What this phase does NOT deliver:**
- The `/linkedout-setup` skill (Phase 9) — that generates config.yaml/secrets.yaml
- Logging infrastructure changes (Phase 3) — but config vars for logging are defined here
- Constants extraction (Phase 4) — scoring weights, thresholds, etc. stay hardcoded for now
- Embedding provider abstraction (Phase 5) — but config vars for providers are defined here

---

## Decision Doc References

| Decision | Doc | Key Constraints |
|----------|-----|-----------------|
| Config hierarchy & layout | `docs/decision/env-config-design.md` | Three-layer: env > config.yaml > secrets.yaml > defaults. Unified `~/linkedout-data/`. `LINKEDOUT_` prefix for custom vars. Industry-standard names kept (`DATABASE_URL`, `OPENAI_API_KEY`). |
| Data directory | `docs/decision/2026-04-07-data-directory-convention.md` | Default `~/linkedout-data/`, override via `LINKEDOUT_DATA_DIR` |
| CLI surface | `docs/decision/cli-surface.md` | `linkedout config show` and `linkedout config path` — no get/set. Config commands implemented in Phase 6 alongside other CLI work. |
| Logging | `docs/decision/logging-observability-strategy.md` | Keep loguru, human-readable default, log dir under `~/linkedout-data/logs/`. Config vars defined here, implementation in Phase 3. |
| Queue removal | `docs/decision/queue-strategy.md` | Procrastinate removed — no queue config vars needed. |
| Embedding model | `docs/decision/2026-04-07-embedding-model-selection.md` | nomic-embed-text-v1.5 default local, OpenAI optional. Config vars: `LINKEDOUT_EMBEDDING_PROVIDER`, `LINKEDOUT_EMBEDDING_MODEL`. |

---

## Current State (What Exists Today)

### Backend Config (`backend/src/shared/config/config.py`)
- `AppConfig(BaseSettings)` composed from `LLMConfig` + `ReliabilityConfig`
- Loads from `.env.local` / `.env.test` / `.env.prod` based on `ENVIRONMENT` var
- Env vars: `DATABASE_URL`, `ENVIRONMENT`, `DEBUG`, `LOG_LEVEL`, `BACKEND_PORT`, `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_MODEL`, `ENABLE_TRACING`, `OPENAI_API_KEY`, etc.
- No YAML support, no `LINKEDOUT_` prefix, no secrets separation
- Global instance: `backend_config = get_config()`

### Backend Startup (`backend/main.py`)
- `dotenv.load_dotenv(_get_env_file())` loads the env-specific file
- CORS origins hardcoded to `['*']`
- Procrastinate worker started in lifespan (to be removed in Phase 6)
- Firebase auth initialization (to be removed in Phase 6)

### Extension Config (`extension/lib/constants.ts`)
- All values hardcoded: `API_BASE_URL = 'http://localhost:8001'`, `TENANT_ID`, `BU_ID`, `APP_USER_ID`, rate limits, staleness days
- No runtime configurability

### Dependencies
- `pydantic-settings` already in `requirements.txt`
- `python-dotenv` already in `requirements.txt`
- `PyYAML` NOT in `requirements.txt` — needs adding

---

## Task Breakdown

### 2A. `.env.example` in Repo Root [Size: S]

**What:** Create `.env.example` at repo root with all env vars documented, grouped by category.

**File:** `backend/.env.example`

**Content:** Copy the `.env.example` template from `docs/decision/env-config-design.md` verbatim — it's already been approved.

**Acceptance criteria:**
- [ ] File exists at `backend/.env.example`
- [ ] Every env var from the decision doc's "Complete Environment Variable Table" is listed
- [ ] Groups match: Core, Server, Embeddings, LLM, API Keys, Logging, Langfuse, Extension Runtime
- [ ] Comments explain each var's purpose and default
- [ ] Header notes that `config.yaml` + `secrets.yaml` is the preferred approach
- [ ] `.gitignore` includes `.env` but NOT `.env.example`

---

### 2B. New Config Module (`LinkedOutSettings`) [Size: L]

**What:** Replace `backend/src/shared/config/config.py` with a new pydantic-settings class implementing the three-layer config hierarchy.

**Files to create:**
- `backend/src/shared/config/settings.py` — new `LinkedOutSettings` class
- `backend/src/shared/config/yaml_sources.py` — `YamlConfigSource` and `YamlSecretsSource`

**Files to modify:**
- `backend/src/shared/config/__init__.py` — export new settings
- `backend/src/shared/config/config.py` — keep temporarily as facade, delegate to new settings

**Implementation details:**

1. **`settings.py`** — `LinkedOutSettings(BaseSettings)` with:
   - All fields from the env var table in `docs/decision/env-config-design.md`
   - `model_config = SettingsConfigDict(env_prefix='LINKEDOUT_', ...)`
   - `validation_alias` for industry-standard vars (`DATABASE_URL`, `OPENAI_API_KEY`, `APIFY_API_KEY`, `LANGFUSE_*`)
   - Computed `backend_url` from `backend_host` + `backend_port` if not explicitly set
   - Path expansion for `data_dir`, `log_dir` (expand `~`)
   - Custom `settings_customise_sources()` for YAML loading order
   - Startup validation: fail fast with actionable error if `DATABASE_URL` missing
   - Data directory creation: ensure `~/linkedout-data/` tree exists on first access

2. **`yaml_sources.py`** — Two custom pydantic-settings sources:
   - `YamlConfigSource` reads `{data_dir}/config/config.yaml`
   - `YamlSecretsSource` reads `{data_dir}/config/secrets.yaml`
   - Both return empty dict if file doesn't exist
   - `YamlSecretsSource` warns if file permissions are not `0600`

3. **Backward compatibility during Phase 2:**
   - Keep `config.py` with `AppConfig = LinkedOutSettings` alias
   - Keep `backend_config = get_config()` working
   - `get_config()` returns a `LinkedOutSettings` instance
   - Old env var names (`ENVIRONMENT`, `BACKEND_PORT`, `LOG_LEVEL`, etc.) no longer supported — clean break per SJ decision

**Dependency addition:**
- Add `PyYAML>=6.0` to `backend/requirements.txt`

**Acceptance criteria:**
- [ ] `LinkedOutSettings` loads from env vars alone (no YAML files needed)
- [ ] `LinkedOutSettings` loads from `config.yaml` when present
- [ ] `LinkedOutSettings` loads from `secrets.yaml` when present
- [ ] Env vars override YAML values
- [ ] `~` is expanded in all path fields
- [ ] Missing `DATABASE_URL` produces clear, actionable error message
- [ ] `PyYAML` added to requirements
- [ ] Existing `backend_config` / `get_config()` still works (returns new settings)
- [ ] Unit tests cover: env-only loading, YAML-only loading, env-overrides-YAML, missing required fields

---

### 2C. Data Directory Structure [Size: S]

**What:** On first access to settings, create the `~/linkedout-data/` directory tree if it doesn't exist.

**File:** `backend/src/shared/config/settings.py` (method on `LinkedOutSettings`)

**Directory tree to create:**
```
~/linkedout-data/
├── config/
├── db/
├── crawled/
├── uploads/
├── logs/
├── queries/
├── reports/
├── metrics/
├── seed/
└── state/
```

**Implementation:** A `ensure_data_dirs()` method called during settings initialization (or lazily on first access). Uses `pathlib.Path.mkdir(parents=True, exist_ok=True)` for each subdirectory.

**Acceptance criteria:**
- [ ] Directories created on first settings access
- [ ] `LINKEDOUT_DATA_DIR` override respected
- [ ] `exist_ok=True` — safe to call repeatedly (idempotent)
- [ ] No error if dirs already exist
- [ ] Test: custom `LINKEDOUT_DATA_DIR` creates tree at custom path

---

### 2D. Secrets Handling [Size: S]

**What:** Implement `secrets.yaml` loading with permission warnings.

**File:** `backend/src/shared/config/yaml_sources.py` (part of `YamlSecretsSource`)

**Implementation:**
- Load `~/linkedout-data/config/secrets.yaml` via PyYAML
- Check file permissions on Unix: warn to stderr if not `0600` (like SSH does)
- Skip permission check on Windows
- Keys in secrets.yaml map to the same field names as env vars (lowercase): `openai_api_key`, `apify_api_key`, `langfuse_public_key`, `langfuse_secret_key`

**Acceptance criteria:**
- [ ] API keys loadable from `secrets.yaml`
- [ ] Warning emitted if permissions are too open (not `0600`)
- [ ] Env var overrides secrets.yaml value
- [ ] Missing file is not an error (returns empty dict)
- [ ] Test: secrets loaded correctly, env var override works

---

### 2E. Agent Context File Generation [Size: S]

**What:** Add a utility function to generate `~/linkedout-data/config/agent-context.env` — the file that Claude skills source for DB access and RLS context.

**File:** `backend/src/shared/config/agent_context.py` (new)

**Content of generated file:**
```bash
# Auto-generated by LinkedOut setup — do not edit manually
# Source this file in CLAUDE.md or skill definitions for DB access
DATABASE_URL=postgresql://linkedout:PASSWORD@localhost:5432/linkedout
LINKEDOUT_TENANT_ID=tenant_sys_001
LINKEDOUT_BU_ID=bu_sys_001
LINKEDOUT_USER_ID=usr_sys_001
```

**Implementation:**
- `generate_agent_context(settings: LinkedOutSettings) -> Path` function
- Reads `DATABASE_URL` from current settings
- Uses the system default tenant/BU/user IDs from `extension/lib/constants.ts` (hardcode same values: `tenant_sys_001`, `bu_sys_001`, `usr_sys_001`)
- Writes to `{data_dir}/config/agent-context.env`
- Overwrites on each call (idempotent)

**Note:** This function is called by `/linkedout-setup` (Phase 9), not during normal startup. It's defined here because it's config infrastructure.

**Acceptance criteria:**
- [ ] Function generates valid env file
- [ ] `DATABASE_URL` from current settings included
- [ ] System tenant/BU/user IDs included
- [ ] File is overwrite-safe
- [ ] Test: file content matches expected format

---

### 2F. Startup Validation & Config Error Messages [Size: M]

**What:** Ensure the config system fails fast with clear, actionable error messages when required values are missing or invalid.

**File:** `backend/src/shared/config/settings.py`

**Validation rules:**
1. `DATABASE_URL` — required. If missing: show the three ways to set it (config.yaml, env var, .env file) and suggest running `/linkedout-setup`
2. `OPENAI_API_KEY` — required only if `embedding_provider == 'openai'`. If missing when needed: explain why it's needed, suggest switching to local provider
3. `LINKEDOUT_DATA_DIR` — must be an expandable path. If expansion fails, show the raw value and suggest using absolute path
4. `LINKEDOUT_BACKEND_PORT` — must be 1-65535 range
5. `LINKEDOUT_LOG_LEVEL` — must be one of DEBUG/INFO/WARNING/ERROR

**Implementation:** Use pydantic validators (`@field_validator`) with custom error messages. Override `ValidationError` rendering to produce the actionable multi-line error format shown in the decision doc.

**Acceptance criteria:**
- [ ] Missing `DATABASE_URL` produces the exact error format from decision doc
- [ ] Missing `OPENAI_API_KEY` only errors when `embedding_provider=openai`
- [ ] Invalid port number produces clear error
- [ ] Invalid log level produces clear error with valid options listed
- [ ] Test: each validation scenario covered

---

### 2G. Update Backend Startup (`main.py`) [Size: M]

**What:** Replace the current env-file loading in `main.py` with the new config system.

**File:** `backend/main.py`

**Changes:**
1. Remove `_get_env_file()` function and `dotenv.load_dotenv()` call
2. Replace with `from shared.config import get_config; settings = get_config()`
3. Use `settings.backend_host` and `settings.backend_port` for uvicorn
4. Use `settings.cors_origins` for CORS middleware (if set), otherwise keep `['*']` for local dev
5. Use `settings.log_level` for logging setup
6. Remove `ENVIRONMENT`-based env file selection entirely
7. Keep Procrastinate and Firebase code for now — Phase 6 removes them

**Acceptance criteria:**
- [ ] Backend starts with `DATABASE_URL` env var alone
- [ ] Backend starts with `config.yaml` alone
- [ ] No reference to `.env.local` / `.env.test` / `.env.prod`
- [ ] No reference to `_get_env_file()`
- [ ] `python-dotenv` import removed from main.py (can stay in requirements for other uses)
- [ ] All existing tests still pass (may need test fixtures updated)

---

### 2H. Update All Config Consumers [Size: L]

**What:** Find and update every file that reads config via the old pattern (`backend_config.X`, `os.getenv()`, direct env var reads) to use the new `LinkedOutSettings`.

**Files to audit (based on codebase exploration):**

Backend modules using config:
- `backend/src/shared/config/config.py` — facade (keep working)
- `backend/src/shared/utilities/logger.py` — reads `LOG_LEVEL`, `ENVIRONMENT`
- `backend/src/utilities/llm_client/` — reads `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`, etc.
- `backend/src/linkedout/enrichment_pipeline/` — reads Apify config
- `backend/src/shared/auth/` — reads Firebase config (keep but guard)
- `backend/src/organization/` — reads tenant config
- `backend/main.py` — reads `BACKEND_PORT`, `BINDING_HOST`, etc.
- `backend/conftest.py` — test config setup

**Approach:**
1. `grep -r "os.getenv\|os.environ\|backend_config\." backend/src/` to find all consumers
2. Replace each with `from shared.config import get_config; settings = get_config()` and `settings.field_name`
3. For the LLM config fields (`LLM_PROVIDER`, `LLM_MODEL`, etc.), map old names to new `LinkedOutSettings` field names
4. For Firebase/auth config — leave the code but ensure it reads from the new config (or is guarded by a feature flag)

**Acceptance criteria:**
- [ ] Zero `os.getenv()` calls in `backend/src/` for config values covered by `LinkedOutSettings`
- [ ] All modules use `get_config()` / `settings.X` pattern
- [ ] No references to old env var names (`ENVIRONMENT`, `BACKEND_PORT` without prefix, `ENABLE_TRACING`, etc.)
- [ ] `grep -r "\.env\.local\|\.env\.test\|\.env\.prod" backend/src/` returns nothing
- [ ] All existing tests pass

---

### 2I. Extension Config Refactor [Size: M]

**What:** Replace hardcoded values in `extension/lib/constants.ts` with a config module that reads from `browser.storage.local` with fallbacks.

**Files:**
- Create: `extension/lib/config.ts`
- Modify: `extension/lib/constants.ts` — keep as re-export facade or inline into config.ts
- Modify: `extension/wxt.config.ts` — add `VITE_BACKEND_URL` env var support
- Modify: All files importing from `constants.ts` — update to use `getConfig()` or keep constants for truly-constant values

**Implementation:**

1. **`extension/lib/config.ts`** (new):
   ```typescript
   export interface ExtensionConfig {
     backendUrl: string;
     stalenessDays: number;
     hourlyLimit: number;
     dailyLimit: number;
   }

   const DEFAULTS: ExtensionConfig = {
     backendUrl: import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
     stalenessDays: 30,
     hourlyLimit: 30,
     dailyLimit: 150,
   };

   export async function getConfig(): Promise<ExtensionConfig> {
     const stored = await browser.storage.local.get('linkedout_config');
     return { ...DEFAULTS, ...stored.linkedout_config };
   }
   ```

2. **Keep in `constants.ts`** (truly constant, not configurable):
   - `TENANT_ID`, `BU_ID`, `APP_USER_ID` — system defaults, never change
   - Voyager decoration ID — LinkedIn API constant
   - `PAGE_DELAY_MIN_MS`, `PAGE_DELAY_MAX_MS` — internal timing

3. **Move to `config.ts`** (user-configurable):
   - `API_BASE_URL` → `backendUrl`
   - `STALENESS_DAYS` → `stalenessDays`
   - `HOURLY_LIMIT` → `hourlyLimit`
   - `DAILY_LIMIT` → `dailyLimit`

4. **Update `wxt.config.ts`:**
   - Ensure `VITE_BACKEND_URL` is recognized as a build-time env var

5. **Update consumers:**
   - Files that import `API_BASE_URL` from constants → use cached config
   - **Config caching strategy (review finding 2026-04-07):** Load config once in `background.ts` at extension startup, cache in a module-level variable. Export synchronous `getConfigSync()` for consumers. This avoids making every API call async-config-aware. The `getConfig()` async function is only called once at startup and when the options page saves new settings.
   - Pattern: `background.ts` calls `await loadConfig()` on startup → populates module-level `_cachedConfig`. All other files import `getConfigSync()` which returns the cached value.

**Acceptance criteria:**
- [ ] `extension/lib/config.ts` exists with `getConfig()` function
- [ ] `API_BASE_URL` no longer hardcoded — reads from config
- [ ] `VITE_BACKEND_URL` env var works at build time
- [ ] Extension builds successfully (`npm run build`)
- [ ] Extension still connects to backend on `localhost:8001` by default
- [ ] Truly-constant values (Voyager IDs, tenant IDs) remain in `constants.ts`

---

### 2J. Test Infrastructure Update [Size: M]

**What:** Update test fixtures and conftest to work with the new config system.

**Files:**
- `backend/conftest.py` — update config fixtures
- `backend/pytest.ini` — update env var settings if needed
- Any test files that set env vars directly

**Implementation:**
1. Create a test `config.yaml` fixture or use env var overrides in pytest
2. Ensure `DATABASE_URL` is set via `pytest.ini` or conftest env setup
3. Mock or override `LINKEDOUT_DATA_DIR` to use a temp directory in tests
4. Ensure no test writes to `~/linkedout-data/` (use tmp dirs)

**Acceptance criteria:**
- [ ] `pytest` runs without needing real `config.yaml` or `secrets.yaml`
- [ ] Tests use temp directories for `LINKEDOUT_DATA_DIR`
- [ ] No test pollutes the real `~/linkedout-data/` directory
- [ ] All existing tests pass with the new config system

---

## Integration Points

### With Phase 1 (OSS Repository Scaffolding)
- `.gitignore` (from Phase 1) must include: `.env`, `config.yaml`, `secrets.yaml`, `*.secret`, `*.key`
- `.env.example` is committed (not ignored)

### With Phase 3 (Logging & Observability)
- Config vars defined here (`LINKEDOUT_LOG_LEVEL`, `LINKEDOUT_LOG_DIR`, `LINKEDOUT_LOG_FORMAT`, etc.) are consumed by Phase 3's logging refactor
- Phase 3 uses `settings.log_level`, `settings.log_dir`, etc.

### With Phase 4 (Constants Externalization)
- Phase 4 adds more fields to `LinkedOutSettings` (scoring weights, thresholds, etc.)
- The config module designed here must be easily extensible — just add fields

### With Phase 5 (Embedding Provider)
- Config vars `LINKEDOUT_EMBEDDING_PROVIDER` and `LINKEDOUT_EMBEDDING_MODEL` defined here
- Phase 5 reads these to select the provider

### With Phase 6 (Code Cleanup)
- Phase 6 removes Procrastinate and Firebase — their config vars are already excluded from `LinkedOutSettings`
- Phase 6 implements CLI commands including `linkedout config show/path`

### With Phase 9 (Setup Flow)
- Setup skill generates `config.yaml`, `secrets.yaml`, and `agent-context.env`
- Uses the `generate_agent_context()` function defined in Task 2E

---

## Testing Strategy

### Unit Tests (Task 2J)
- **Config loading:** env-only, YAML-only, env+YAML, precedence ordering
- **YAML sources:** file exists, file missing, malformed YAML, permission warnings
- **Validation:** missing required fields, invalid values, type coercion
- **Path expansion:** `~` expansion, `LINKEDOUT_DATA_DIR` override
- **Data directory creation:** dirs created on init, idempotent
- **Agent context:** file generation, content correctness

### Integration Tests
- **Backend startup:** boots with minimal env vars (just `DATABASE_URL`)
- **Backend startup:** boots with `config.yaml` only
- **Extension build:** builds with `VITE_BACKEND_URL` env var

### Manual Verification
- Delete all `.env*` files, set only `DATABASE_URL` env var → backend starts
- Create `config.yaml` with `database_url` → backend starts
- Set `LINKEDOUT_DATA_DIR=/tmp/test-linkedout` → dirs created at custom path
- Verify `secrets.yaml` permission warning on non-600 permissions

---

## Exit Criteria Verification Checklist

- [ ] Backend boots with only env vars (no YAML files needed)
- [ ] Backend boots with only `config.yaml` (no env vars beyond PATH etc.)
- [ ] Env vars override YAML values
- [ ] No hardcoded secrets anywhere in the codebase
- [ ] No references to `.env.local` / `.env.test` / `.env.prod` in source code
- [ ] `~/linkedout-data/` directory tree created on first run
- [ ] `secrets.yaml` permission warning works on Linux/Mac
- [ ] Extension builds with configurable backend URL (`VITE_BACKEND_URL`)
- [ ] Extension reads runtime config from `browser.storage.local`
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] `grep -r "os.getenv" backend/src/` returns zero hits for config vars covered by `LinkedOutSettings`

---

## Estimated Complexity

| Task | Size | Rationale |
|------|------|-----------|
| 2A. `.env.example` | S | Copy from decision doc, minor formatting |
| 2B. Config module (`LinkedOutSettings`) | L | Core of the phase — new pydantic-settings class, YAML sources, field mapping |
| 2C. Data directory structure | S | `mkdir -p` equivalent, few lines of code |
| 2D. Secrets handling | S | Part of YAML sources, plus permission check |
| 2E. Agent context file | S | Simple file generation utility |
| 2F. Startup validation | M | Custom validators with actionable error messages |
| 2G. Update `main.py` | M | Remove old loading, wire in new config, test startup paths |
| 2H. Update all config consumers | L | Many files to touch, need to audit entire codebase |
| 2I. Extension config refactor | M | New module + update consumers, async config pattern |
| 2J. Test infrastructure | M | Update fixtures, temp dir handling, ensure isolation |

**Total:** ~3 S + 3 M + 2 L tasks

**Suggested execution order:**
1. 2A (`.env.example`) — independent, quick win
2. 2B + 2C + 2D (config module + dirs + secrets) — core work, tightly coupled
3. 2E (agent context) — depends on 2B
4. 2F (validation) — depends on 2B
5. 2G (main.py) — depends on 2B
6. 2H (update consumers) — depends on 2B, largest effort
7. 2I (extension config) — independent of backend work, can parallel with 2H
8. 2J (tests) — last, after all changes
9. 2K (basic CI) — after tests pass, set up initial GitHub Actions workflow

### 2K. Basic CI Workflow [Size: S]

**What (review finding 2026-04-07):** Set up a minimal GitHub Actions CI workflow so that all subsequent phases have a safety net from day one. Without CI, regressions introduced in Phases 3-13 won't be caught until Phase 13.

**File to create:** `.github/workflows/ci.yml`

**Scope (minimal):**
- Trigger on push to `main` and PRs
- Python 3.11 + PostgreSQL 16 service container
- `uv sync` + `uv run pytest backend/tests/unit/ -x`
- `uv run ruff check backend/src/`
- No matrix, no macOS, no installation tests — those come in Phase 13

**Acceptance criteria:**
- [ ] CI runs on every push to main and every PR
- [ ] Unit tests execute and report pass/fail
- [ ] Ruff linting runs
- [ ] Workflow takes < 3 minutes

---

## Open Questions

1. **`LLMConfig` and `ReliabilityConfig` preservation:** The current config composes `LLMConfig` (LLM model names, retry settings, prompt settings) and `ReliabilityConfig` (timeouts, rate limits). Should these be flattened into `LinkedOutSettings` or kept as nested models? **Recommendation:** Flatten — pydantic-settings handles flat env vars better, and nesting complicates YAML mapping. But this touches many consumers.

2. **`conftest.py` env setup:** The current `conftest.py` (682 lines) has extensive env var setup for tests. The migration to new config will need careful attention here. Some test env vars may need to change names. **Recommendation:** Run the full test suite early after 2B to identify breakage.

3. **Extension async config loading:** Moving from synchronous `constants.ts` imports to async `getConfig()` calls touches many files in the extension. An alternative is to load config once at extension startup and cache it in a module-level variable. **Recommendation:** Cache at startup — simpler for consumers, still configurable.

4. **pydantic-settings `customise_sources` API stability:** The `settings_customise_sources` API changed between pydantic-settings v1 and v2. Need to verify which version is installed and use the correct API. **Recommendation:** Check `pip show pydantic-settings` and pin the version in requirements.

5. **`CORS_ORIGINS` default:** Currently hardcoded to `['*']` in `main.py`. The decision doc defines `LINKEDOUT_CORS_ORIGINS` as a config var defaulting to `http://localhost:8001`. Should we tighten CORS in this phase or keep `['*']` for dev convenience? **Recommendation:** Keep `['*']` as default for now — tightening CORS is a Phase 6 cleanup item when the backend is only needed for the extension.

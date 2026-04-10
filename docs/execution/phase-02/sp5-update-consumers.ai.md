# SP5: Update All Config Consumers

**Sub-phase:** 5 of 7
**Tasks covered:** 2H
**Size:** L (largest effort — many files to touch)
**Dependencies:** SP2 (config module), SP4 (main.py already migrated)
**Estimated effort:** 60-90 minutes

---

## Objective

Find and update every backend file that reads config via the old pattern (`backend_config.X`, `os.getenv()`, `os.environ`, direct env var reads) to use the new `LinkedOutSettings` via `get_config()`.

---

## Steps

### 1. Audit All Config Consumers

Run these searches to find every file that needs updating:

```bash
# Direct env reads
grep -rn "os\.getenv\|os\.environ" backend/src/

# Old config object
grep -rn "backend_config\." backend/src/

# Old config imports
grep -rn "from.*config.*import.*AppConfig\|from.*config.*import.*LLMConfig\|from.*config.*import.*ReliabilityConfig" backend/src/

# Old env var names (no LINKEDOUT_ prefix)
grep -rn "ENVIRONMENT\|BACKEND_PORT\|BINDING_HOST\|LOG_LEVEL\|ENABLE_TRACING\|EMBEDDING_MODEL" backend/src/ --include="*.py"

# Old env file references
grep -rn "\.env\.local\|\.env\.test\|\.env\.prod" backend/src/
```

### 2. Map Old Names to New Fields

Use this mapping when updating consumers:

| Old Access Pattern | New Access Pattern |
|---|---|
| `os.getenv('DATABASE_URL')` | `get_config().database_url` |
| `os.getenv('ENVIRONMENT')` | `get_config().environment` |
| `os.getenv('DEBUG')` | `get_config().debug` |
| `os.getenv('LOG_LEVEL')` | `get_config().log_level` |
| `os.getenv('BACKEND_PORT')` | `get_config().backend_port` |
| `os.getenv('BINDING_HOST')` | `get_config().backend_host` |
| `os.getenv('LLM_PROVIDER')` | `get_config().llm_provider` |
| `os.getenv('LLM_MODEL')` | `get_config().llm_model` |
| `os.getenv('EMBEDDING_MODEL')` | `get_config().embedding_model` |
| `os.getenv('OPENAI_API_KEY')` | `get_config().openai_api_key` |
| `os.getenv('APIFY_API_KEY')` | `get_config().apify_api_key` |
| `os.getenv('ENABLE_TRACING')` | `get_config().langfuse_enabled` |
| `backend_config.llm_provider` | `get_config().llm_provider` |
| `backend_config.llm_model` | `get_config().llm_model` |
| `backend_config.embedding_model` | `get_config().embedding_model` |
| `backend_config.enable_tracing` | `get_config().langfuse_enabled` |

### 3. Update Each File

For each file found in the audit:

1. Replace the import: `from shared.config import get_config`
2. Replace the access pattern: `settings = get_config()` then `settings.field_name`
3. Remove any `os.getenv()` calls for config values covered by `LinkedOutSettings`
4. Keep `os.getenv()` for values NOT in `LinkedOutSettings` (e.g., system env vars like `PATH`, `HOME`)

**Known files to update (from phase plan):**
- `backend/src/shared/utilities/logger.py` — reads `LOG_LEVEL`, `ENVIRONMENT`
- `backend/src/utilities/llm_client/` — reads `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_API_KEY`
- `backend/src/linkedout/enrichment_pipeline/` — reads Apify config
- `backend/src/shared/auth/` — reads Firebase config (keep but ensure it reads from new config or guards with feature flag)
- `backend/src/organization/` — reads tenant config
- `backend/conftest.py` — test config setup (handle in SP7, not here)

### 4. Handle Special Cases

**Apify key rotation:** The old code may have `APIFY_API_KEY_1` through `APIFY_API_KEY_9` for round-robin. Replace with single `apify_api_key` field. OSS = single user, single key.

**Firebase auth:** If auth code reads env vars directly, update to use settings but DO NOT remove the auth code — Phase 6 handles removal.

**LLM client config:** The old `LLMConfig` class may have fields not yet mapped. Read the current `LLMConfig` class and ensure all its fields are covered by `LinkedOutSettings` (or explicitly dropped with a comment).

### 5. Verify No Old Patterns Remain

```bash
# Should return zero hits for config-related env reads
grep -rn "os\.getenv.*DATABASE_URL\|os\.getenv.*ENVIRONMENT\|os\.getenv.*LOG_LEVEL\|os\.getenv.*BACKEND_PORT\|os\.getenv.*LLM_PROVIDER\|os\.getenv.*EMBEDDING_MODEL\|os\.getenv.*OPENAI_API_KEY\|os\.getenv.*APIFY_API_KEY\|os\.getenv.*ENABLE_TRACING" backend/src/

# Should return zero hits
grep -rn "\.env\.local\|\.env\.test\|\.env\.prod" backend/src/
```

---

## Verification

```bash
# No os.getenv for config values
HITS=$(grep -rn "os\.getenv" backend/src/ --include="*.py" | grep -v "conftest\|test_" | grep -c "DATABASE_URL\|ENVIRONMENT\|LOG_LEVEL\|BACKEND_PORT\|LLM_PROVIDER\|LLM_MODEL\|EMBEDDING_MODEL\|OPENAI_API_KEY\|APIFY_API_KEY\|ENABLE_TRACING")
[ "$HITS" -eq 0 ] && echo "PASS: no old env reads" || echo "FAIL: $HITS old env reads remain"

# No old env file references
grep -rn "\.env\.local\|\.env\.test\|\.env\.prod" backend/src/ && echo "FAIL" || echo "PASS: no old env file refs"

# All modules import from shared.config
# (This is a spot-check — verify each changed file individually)

# Existing tests still pass (basic smoke test)
cd backend && python -m pytest --co -q 2>&1 | tail -5  # just collection, not execution
```

---

## Acceptance Criteria

- [ ] Zero `os.getenv()` calls in `backend/src/` for config values covered by `LinkedOutSettings`
- [ ] All modules use `get_config()` / `settings.X` pattern
- [ ] No references to old env var names (`ENVIRONMENT`, `BACKEND_PORT` without prefix, `ENABLE_TRACING`)
- [ ] No references to `.env.local` / `.env.test` / `.env.prod` in `backend/src/`
- [ ] Old `LLMConfig` and `ReliabilityConfig` fields mapped to `LinkedOutSettings` fields
- [ ] Apify round-robin (`APIFY_API_KEY_1..9`) replaced with single `apify_api_key`
- [ ] Firebase/auth code still works (reads from new config, not removed)

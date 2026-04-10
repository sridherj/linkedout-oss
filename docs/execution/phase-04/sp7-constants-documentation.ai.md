# SP7: Constants Documentation

**Sub-phase:** 7 of 7
**Plan task:** 4H (Constants Documentation)
**Dependencies:** SP1–SP6 (all audits and extractions must be complete)
**Estimated complexity:** M
**Changes code:** Yes (documentation files and .env.example)

---

## Objective

Create comprehensive documentation for every externalized constant and update `.env.example` and `config.yaml` template with all new config variables.

---

## Steps

### 1. Create `docs/configuration.md`

Create a complete configuration reference guide covering ALL configurable values across both backend and extension. Follow this structure:

```
# LinkedOut Configuration Reference

## 1. Quick Start
   - Most common settings you'll want to change
   - Copy-paste examples for common setups

## 2. Core Settings
   - DATABASE_URL, LINKEDOUT_DATA_DIR, LINKEDOUT_DEBUG, LINKEDOUT_ENVIRONMENT

## 3. Server Settings
   - LINKEDOUT_BACKEND_HOST, LINKEDOUT_BACKEND_PORT, LINKEDOUT_CORS_ORIGINS

## 4. Embedding Settings
   - embedding.model, embedding.dimensions, embedding.chunk_size, embedding.batch_timeout_seconds
   - Provider-specific defaults (OpenAI vs local/nomic)
   - Dimension validation behavior

## 5. LLM Settings
   - llm.model, llm.search_model, llm.timeout_seconds, llm.retry_*
   - Rate limiting, prompt cache

## 6. Enrichment Settings
   - enrichment.apify_base_url, enrichment.cache_ttl_days, enrichment.cost_per_profile_usd
   - All timeout settings

## 7. Scoring Settings
   - scoring.weight_*, scoring.dunbar_*, scoring.seniority_boosts
   - Explanation of what each weight affects

## 8. Logging Settings
   - LINKEDOUT_LOG_LEVEL, LINKEDOUT_LOG_ROTATION, LINKEDOUT_LOG_RETENTION
   - Per-module overrides

## 9. Extension Settings (browser.storage.local)
   - backendUrl, stalenessDays, hourlyLimit, dailyLimit
   - How to set via DevTools (Phase 12 adds options page)

## 10. Constants Reference (Non-Configurable)
   - Apify Actor ID — why it's not configurable
   - Nanoid sizes — data-format constants
   - Voyager decoration IDs — fragile LinkedIn internals
   - Tenant/BU/User IDs — single-user OSS defaults
   - Entity ID prefixes — data-format constants
   - pgvector dimension (1536) — schema-level, requires migration
```

**For each configurable value, document:**
- Config key (YAML path)
- Environment variable name
- Default value
- Valid range/type
- What it affects (plain English)
- Which component uses it (backend, extension, or both)

### 2. Update `backend/.env.example`

Add ALL new env vars introduced by SP2–SP6. Include documentation comments for each section. Follow the existing format in the file (see `docs/decision/env-config-design.md` for the template).

New sections to add:
```bash
# ── Scoring (nested config — use double underscore) ──────
# LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP=0.40
# LINKEDOUT_SCORING__WEIGHT_EXTERNAL_CONTACT=0.25
# LINKEDOUT_SCORING__WEIGHT_EMBEDDING_SIMILARITY=0.15
# LINKEDOUT_SCORING__WEIGHT_SOURCE_COUNT=0.10
# LINKEDOUT_SCORING__WEIGHT_RECENCY=0.10
# LINKEDOUT_SCORING__DUNBAR_INNER_CIRCLE=15
# LINKEDOUT_SCORING__DUNBAR_ACTIVE=50
# LINKEDOUT_SCORING__DUNBAR_FAMILIAR=150

# ── Enrichment ───────────────────────────────────────────
# LINKEDOUT_ENRICHMENT__CACHE_TTL_DAYS=90
# LINKEDOUT_ENRICHMENT__COST_PER_PROFILE_USD=0.004
# LINKEDOUT_ENRICHMENT__SYNC_TIMEOUT_SECONDS=60
# LINKEDOUT_ENRICHMENT__RUN_POLL_TIMEOUT_SECONDS=300

# ── LLM ──────────────────────────────────────────────────
# LINKEDOUT_LLM__MODEL=gpt-5.2-2025-12-11
# LINKEDOUT_LLM__SEARCH_MODEL=gpt-5.4-mini
# LINKEDOUT_LLM__TIMEOUT_SECONDS=120.0
# LINKEDOUT_LLM__RETRY_MAX_ATTEMPTS=3

# ── Embeddings ───────────────────────────────────────────
# LINKEDOUT_EMBEDDING__MODEL=text-embedding-3-small
# LINKEDOUT_EMBEDDING__DIMENSIONS=1536
# LINKEDOUT_EMBEDDING__CHUNK_SIZE=5000

# ── Log Rotation ─────────────────────────────────────────
# LINKEDOUT_LOG_ROTATION=50 MB
# LINKEDOUT_LOG_RETENTION=30 days

# ── Pagination ───────────────────────────────────────────
# LINKEDOUT_DEFAULT_PAGE_SIZE=20
```

### 3. Update config.yaml template

Consolidate all the config.yaml sections from SP2–SP6 into a complete template. This should be documented in `docs/configuration.md` and/or shipped as a template file.

---

## Verification

- [ ] `docs/configuration.md` exists and covers ALL configurable values from SP2–SP6
- [ ] Every constant from the audit documents (SP1) that was externalized has a corresponding entry in `docs/configuration.md`
- [ ] `.env.example` includes all new env vars with documentation comments
- [ ] Config.yaml template includes all new sections
- [ ] Each documented value has: config key, env var, default, type, description, component
- [ ] Non-configurable constants are listed with explanations of why
- [ ] Quick Start section makes it easy for new users to find the most important settings

### Exit Criteria Verification (Full Phase 4)

Run the full exit criteria checklist from the phase plan:

- [ ] `docs/audit/backend-constants-audit.md` exists with complete inventory
- [ ] `docs/audit/extension-constants-audit.md` exists with complete inventory
- [ ] `docs/configuration.md` exists with all constants documented
- [ ] `.env.example` updated with all new env vars
- [ ] `grep -rn "gpt-5\|gpt-4\|text-embedding" backend/src/ --include="*.py" | grep -v config.py | grep -v __pycache__` returns zero
- [ ] `grep -rn "localhost:8001" backend/src/ --include="*.py" | grep -v config.py` returns zero
- [ ] `grep -rn "= 1536" backend/src/ --include="*.py" | grep -v config.py | grep -v entities/` returns zero
- [ ] Extension `lib/config.ts` exists with typed `ExtensionConfig` and `getConfig()`
- [ ] Extension `lib/constants.ts` contains only true constants
- [ ] All configurable extension values flow through `getConfig()`
- [ ] Log rotation settings match decision doc (50 MB rotation, 30 days retention)

---

## Notes

- This sub-phase is mostly documentation. Read the output of all prior sub-phases before writing.
- Cross-reference the audit documents (SP1) against what was actually externalized (SP2–SP6) to catch any gaps.
- The `.env.example` update should follow the exact format from `docs/decision/env-config-design.md`.
- For the config.yaml template, all new sections should be commented out (showing defaults) — users who don't customize get the defaults automatically.

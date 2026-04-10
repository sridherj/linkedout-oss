# Phase 4: Constants Externalization — Detailed Execution Plan

**Version:** 1.0
**Date:** 2026-04-07
**Status:** Draft — pending SJ review
**Phase:** 4 of 13
**Dependencies:** Phase 2 (Environment & Configuration System), Phase 3 (Logging & Observability)
**Delivers:** Every hardcoded magic number, URL, threshold, model name, and ID in both backend and extension is externalized to config with a sensible default. Users can customize behavior without editing source code.

---

## Phase Overview

Phase 4 audits and extracts ALL hardcoded constants across the backend (Python) and extension (TypeScript) codebases. The config system built in Phase 2 (`LinkedOutSettings` + `config.yaml` + `secrets.yaml`) provides the target for backend constants. The extension config system (`lib/config.ts` + `browser.storage.local`) provides the target for extension constants.

This phase does NOT add new features — it moves existing hardcoded values into the config layer so they become user-tunable.

### What This Phase Delivers

1. A comprehensive constants audit document (the source of truth for what was externalized)
2. Backend constants centralized in `LinkedOutSettings` (pydantic-settings)
3. Extension constants centralized in `lib/config.ts` (with `browser.storage.local` fallbacks)
4. Updated `.env.example` with all new config variables documented
5. A `docs/configuration.md` reference guide for all tunable constants

### Dependencies on Prior Phases

- **Phase 2 (Config System):** `LinkedOutSettings` pydantic-settings class, `config.yaml`/`secrets.yaml` loading, `LINKEDOUT_` env var prefix convention — all must exist before constants can be moved there.
- **Phase 3 (Logging):** Log rotation settings (`LINKEDOUT_LOG_ROTATION`, `LINKEDOUT_LOG_RETENTION`) and log directory config (`LINKEDOUT_LOG_DIR`) should already be externalized. Phase 4 verifies and fills gaps.

### Integration with Phase 0 Decisions

- **`docs/decision/env-config-design.md`:** Three-layer config hierarchy (env > YAML > defaults). All new constants follow this pattern. `LINKEDOUT_` prefix for LinkedOut-specific vars; industry-standard names (`OPENAI_API_KEY`) keep standard names.
- **`docs/decision/cli-surface.md`:** `linkedout config show` displays all config including newly externalized constants (secrets redacted). No new CLI commands needed.
- **`docs/decision/logging-observability-strategy.md`:** Log rotation (50 MB) and retention (30 days) are already specified. Phase 4 ensures they're wired through config, not hardcoded in `logger.py`.
- **`docs/decision/queue-strategy.md`:** Procrastinate removed. Enrichment runs synchronously. Enrichment timeouts and retry config are externalized here.
- **`docs/decision/2026-04-07-embedding-model-selection.md`:** Default embedding model is `nomic-embed-text-v1.5` for local, `text-embedding-3-small` for OpenAI. Embedding dimensions depend on provider. Phase 4 ensures these are configurable, not hardcoded.

---

## Task Breakdown

### 4A. Backend Constants Audit

**Goal:** Produce a definitive inventory of every hardcoded value in the backend, categorized by type and externalization priority.

**Acceptance Criteria:**
- Audit document at `docs/audit/backend-constants-audit.md`
- Every hardcoded value cataloged with: file path, line number, current value, what it controls, and externalization recommendation (externalize / keep hardcoded / defer)
- Categories: API URLs, model names, rate limits, cache TTLs, retry/timeout, batch sizes, scoring weights, DB settings, port numbers, ID prefixes, log settings, cost tracking, magic numbers

**File-Level Targets:**
- Read (audit only, no changes):
  - `backend/src/shared/config/config.py` — current config centralization point
  - `backend/src/shared/utilities/logger.py` — log rotation settings
  - `backend/src/shared/infra/reliability/retry_policy.py` — retry configs
  - `backend/src/shared/infra/reliability/timeout_policy.py` — timeout configs
  - `backend/src/shared/common/nanoids.py` — ID generation sizes
  - `backend/src/linkedout/enrichment_pipeline/apify_client.py` — Apify URLs, costs, timeouts
  - `backend/src/linkedout/enrichment_pipeline/controller.py` — cache TTL, inline URLs
  - `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` — all scoring weights and thresholds
  - `backend/src/utilities/llm_manager/embedding_client.py` — model names, dimensions, polling
  - `backend/src/dev_tools/generate_embeddings.py` — batch sizes, timeouts
  - `backend/main.py` — server config
- Create:
  - `docs/audit/backend-constants-audit.md`

**Complexity:** M

---

### 4B. Backend Scoring Constants Extraction

**Goal:** Move all affinity scoring weights, Dunbar tier thresholds, seniority boosts, and recency thresholds from hardcoded values in `affinity_scorer.py` into the config system.

**Acceptance Criteria:**
- All scoring weights configurable via `config.yaml` under a `scoring:` section
- Dunbar tier thresholds (15/50/150) configurable
- Seniority boost multipliers configurable
- Recency decay thresholds configurable
- External contact warmth scores configurable
- Default values match current hardcoded values exactly (no behavioral change)
- `AFFINITY_VERSION` bumps if scoring algorithm changes; stays at 3 if only config extraction

**File-Level Targets:**
- Modify:
  - `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` — replace hardcoded constants with config reads
  - `backend/src/shared/config/config.py` (or the Phase 2 `LinkedOutSettings` class) — add scoring config fields
- Update:
  - `~/linkedout-data/config/config.yaml` template — add `scoring:` section (commented out, showing defaults)

**Constants to Extract:**

| Constant | Current Value | Config Key |
|----------|--------------|------------|
| `WEIGHT_CAREER_OVERLAP` | `0.40` | `scoring.weight_career_overlap` |
| `WEIGHT_EXTERNAL_CONTACT` | `0.25` | `scoring.weight_external_contact` |
| `WEIGHT_EMBEDDING_SIMILARITY` | `0.15` | `scoring.weight_embedding_similarity` |
| `WEIGHT_SOURCE_COUNT` | `0.10` | `scoring.weight_source_count` |
| `WEIGHT_RECENCY` | `0.10` | `scoring.weight_recency` |
| Dunbar inner circle | `15` | `scoring.dunbar_inner_circle` |
| Dunbar active | `50` | `scoring.dunbar_active` |
| Dunbar familiar | `150` | `scoring.dunbar_familiar` |
| Seniority boosts | `{founder: 3.0, ...}` | `scoring.seniority_boosts` (dict) |
| External contact scores | `{phone: 1.0, email: 0.7}` | `scoring.external_contact_scores` (dict) |
| Career normalization window | `36` months | `scoring.career_normalization_months` |
| Recency thresholds | `[(12, 1.0), (36, 0.7), (60, 0.4)]` | `scoring.recency_thresholds` (list of tuples) |

**Design Note:** Use a nested pydantic model (`ScoringConfig`) within `LinkedOutSettings`. Env var override pattern: `LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP=0.35` (double underscore for nesting, per pydantic-settings convention).

**Complexity:** M

---

### 4C. Backend Enrichment Constants Extraction

**Goal:** Move all enrichment-related constants (Apify settings, cache TTLs, timeouts, costs) from scattered inline values into config.

**Acceptance Criteria:**
- Apify Actor ID kept as a hardcoded named constant (NOT configurable — resolved decision Q4). Include explanation comment and link to Apify marketplace listing. Changing it breaks response parsing.
- Apify base URL configurable
- Enrichment cache TTL configurable (currently 90 days)
- Cost per profile configurable (currently $0.004)
- All Apify-related timeouts configurable
- Retry settings for enrichment configurable
- Default values match current hardcoded values exactly

**File-Level Targets:**
- Modify:
  - `backend/src/linkedout/enrichment_pipeline/apify_client.py` — replace `BASE_URL`, `ACTOR_ID`, `COST_PER_PROFILE_USD`, `ACTOR_SCRAPER_MODE`, and all inline timeout values with config reads
  - `backend/src/linkedout/enrichment_pipeline/controller.py` — replace `CACHE_DAYS` (90), inline Apify validation URL, and timeout (15s) with config reads
  - `backend/src/shared/config/config.py` (or `LinkedOutSettings`) — add enrichment config fields

**Constants to Extract:**

| Constant | Current Value | Config Key |
|----------|--------------|------------|
| Apify base URL | `https://api.apify.com/v2` | `enrichment.apify_base_url` |
| Apify actor ID | `LpVuK3Zozwuipa5bp` | **NOT configurable** — keep as named constant `APIFY_LINKEDIN_ACTOR_ID` with comment explaining why (parsing coupled to this actor's response schema) |
| Cost per profile | `0.004` | `enrichment.cost_per_profile_usd` |
| Cache TTL | `90` days | `enrichment.cache_ttl_days` (also `LINKEDOUT_ENRICHMENT_CACHE_TTL_DAYS` per env-config-design.md) |
| Sync enrichment timeout | `60` s | `enrichment.sync_timeout_seconds` |
| Async start timeout | `30` s | `enrichment.async_start_timeout_seconds` |
| Run poll timeout | `300` s | `enrichment.run_poll_timeout_seconds` |
| Run poll interval | `5` s | `enrichment.run_poll_interval_seconds` |
| Fetch results timeout | `30` s | `enrichment.fetch_results_timeout_seconds` |
| Key validation timeout | `15` s | `enrichment.key_validation_timeout_seconds` |

**Complexity:** M

---

### 4D. Backend LLM & Embedding Constants Extraction

**Goal:** Move all LLM model names, embedding dimensions, retry/timeout policies, and batch sizes from scattered locations into the central config.

**Acceptance Criteria:**
- LLM model names read from config (not hardcoded `gpt-5.2-2025-12-11`, `gpt-5.4-mini`)
- Embedding model name and dimensions read from config
- Embedding dimensions validated for consistency: if provider is `local` (nomic), dimension is 768; if `openai`, dimension is 1536 (or configurable)
- All retry/timeout policies read from config
- Batch sizes for embedding generation configurable
- The pgvector column dimension in `crawled_profile_entity.py` is documented as a schema-level constant (requires migration to change, not runtime-configurable)

**File-Level Targets:**
- Modify:
  - `backend/src/shared/config/config.py` — consolidate model names, dimensions, retry/timeout defaults
  - `backend/src/shared/infra/reliability/retry_policy.py` — read from config instead of hardcoded `RetryConfig` instances
  - `backend/src/shared/infra/reliability/timeout_policy.py` — read from config instead of hardcoded `TimeoutConfig` instances
  - `backend/src/utilities/llm_manager/embedding_client.py` — read model name, dimensions, batch polling interval/timeout from config
  - `backend/src/dev_tools/generate_embeddings.py` — read chunk size and batch timeout from config
- Document (no change, just note):
  - `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py` — pgvector `1536` dimension is a schema constant, changeable only via migration

**Constants to Extract:**

| Constant | Current Value | Config Key |
|----------|--------------|------------|
| Default LLM model | `gpt-5.2-2025-12-11` | `LINKEDOUT_LLM_MODEL` (already in env-config-design.md) |
| Search LLM model | `gpt-5.4-mini` | `LINKEDOUT_SEARCH_LLM_MODEL` |
| Embedding model | `text-embedding-3-small` | `LINKEDOUT_EMBEDDING_MODEL` (already in env-config-design.md) |
| Embedding dimensions | `1536` | `LINKEDOUT_EMBEDDING_DIMENSIONS` (computed from provider if not set) |
| LLM retry max attempts | `3` | `LINKEDOUT_LLM_RETRY_MAX_ATTEMPTS` |
| LLM retry min wait | `2.0` s | `LINKEDOUT_LLM_RETRY_MIN_WAIT` |
| LLM retry max wait | `30.0` s | `LINKEDOUT_LLM_RETRY_MAX_WAIT` |
| LLM timeout | `120.0` s | `LINKEDOUT_LLM_TIMEOUT_SECONDS` |
| External API retry max | `3` | `LINKEDOUT_EXTERNAL_API_RETRY_MAX_ATTEMPTS` |
| External API timeout | `30.0` s | `LINKEDOUT_EXTERNAL_API_TIMEOUT_SECONDS` |
| LLM rate limit (RPM) | `60` | `LINKEDOUT_RATE_LIMIT_LLM_RPM` |
| Prompt cache TTL | `300` s | `LINKEDOUT_PROMPT_CACHE_TTL_SECONDS` |
| Summarize beyond N turns | `4` | `LINKEDOUT_SUMMARIZE_BEYOND_N_TURNS` |
| Embedding chunk size | `5000` | `LINKEDOUT_EMBEDDING_CHUNK_SIZE` |
| Embedding batch timeout | `7200` s | `LINKEDOUT_EMBEDDING_BATCH_TIMEOUT` |
| Embedding batch poll interval | `30` s | `LINKEDOUT_EMBEDDING_BATCH_POLL_INTERVAL` |

**Complexity:** L

---

### 4E. Backend Infrastructure Constants Extraction

**Goal:** Move log rotation settings, pagination defaults, and other infrastructure constants into config.

**Acceptance Criteria:**
- Log rotation size and retention read from config (per logging-observability-strategy.md: 50 MB rotation, 30 days retention)
- Pagination defaults configurable
- Backend port already in config (verify, don't duplicate)
- Nanoid sizes documented but kept hardcoded (changing ID format would break data compatibility)

**File-Level Targets:**
- Modify:
  - `backend/src/shared/utilities/logger.py` — replace hardcoded `500 MB` rotation / `10 days` retention with config values (decision doc says 50 MB / 30 days)
  - `backend/src/shared/config/config.py` — add `LINKEDOUT_LOG_ROTATION` and `LINKEDOUT_LOG_RETENTION` if not already present from Phase 3
- Document (keep hardcoded):
  - `backend/src/shared/common/nanoids.py` — nanoid sizes (21 chars, 8 chars) are data-format constants, not user-tunable
  - Entity ID prefixes throughout the domain — these are data-format constants, not user-tunable

**Constants to Extract:**

| Constant | Current Value | Config Key | Action |
|----------|--------------|------------|--------|
| Log rotation size | `500 MB` (should be `50 MB` per decision) | `LINKEDOUT_LOG_ROTATION` | Extract + fix to match decision |
| Log retention | `10 days` (should be `30 days` per decision) | `LINKEDOUT_LOG_RETENTION` | Extract + fix to match decision |
| Default pagination limit | `20` | `LINKEDOUT_DEFAULT_PAGE_SIZE` | Extract |
| Nanoid size (basic) | `21` | N/A | Keep hardcoded — document |
| Nanoid size (timestamped suffix) | `8` | N/A | Keep hardcoded — document |
| Entity ID prefixes | Various (`co`, `cp`, etc.) | N/A | Keep hardcoded — document |

**Note:** The log rotation values currently in code (`500 MB`, `10 days`) contradict the approved decision (`50 MB`, `30 days`). This task fixes the mismatch.

**Complexity:** S

---

### 4F. Extension Constants Audit

**Goal:** Produce a definitive inventory of every hardcoded value in the Chrome extension.

**Acceptance Criteria:**
- Audit document at `docs/audit/extension-constants-audit.md`
- Every hardcoded value cataloged with: file path, line, current value, what it controls, fragility assessment (fragile/stable), and externalization recommendation
- Voyager decoration IDs explicitly flagged as fragile with breakage risk documented

**File-Level Targets:**
- Read (audit only, no changes):
  - `extension/lib/constants.ts` — primary constants file
  - `extension/lib/rate-limiter.ts` — timing calculations
  - `extension/lib/log.ts` — storage caps
  - `extension/lib/voyager/client.ts` — Voyager API params, decoration IDs
  - `extension/lib/mutual/extractor.ts` — mutual connections params, decoration ID
  - `extension/lib/backend/client.ts` — API endpoints, defaults
  - `extension/entrypoints/voyager.content.ts` — debounce timer, speed multipliers
- Create:
  - `docs/audit/extension-constants-audit.md`

**Complexity:** S

---

### 4G. Extension Constants Extraction

**Goal:** Move user-configurable extension values to `lib/config.ts` with `browser.storage.local` backing. Document fragile constants separately.

**Acceptance Criteria:**
- New `extension/lib/config.ts` module (or expand existing) with typed `ExtensionConfig` interface
- All user-configurable values read from `browser.storage.local` with hardcoded fallbacks
- Voyager decoration IDs remain in `constants.ts` but are clearly documented as fragile LinkedIn internals
- Tenant/BU/User IDs remain as constants (single-user OSS, no need to configure)
- Backend URL configurable at runtime (not just build-time)
- All callers of old hardcoded constants updated to use new config system

**File-Level Targets:**
- Create (or expand):
  - `extension/lib/config.ts` — typed config with `getConfig()` async loader
- Modify:
  - `extension/lib/constants.ts` — reduce to only true constants (Voyager decoration IDs, event names, tenant IDs); configurable values move to `config.ts`
  - `extension/lib/rate-limiter.ts` — read limits from config
  - `extension/lib/log.ts` — read max entries from config
  - `extension/entrypoints/voyager.content.ts` — read debounce timer from config
  - `extension/lib/mutual/extractor.ts` — read page size and max pages from config
  - All files that import from `constants.ts` for configurable values — update imports

**Constants to Extract to `config.ts`:**

| Constant | Current Value | Config Key | Source |
|----------|--------------|------------|--------|
| Backend URL | `http://localhost:8001` | `backendUrl` | `browser.storage.local` / `VITE_BACKEND_URL` |
| Staleness threshold | `30` days | `stalenessDays` | `browser.storage.local` |
| Hourly rate limit | `30` | `hourlyLimit` | `browser.storage.local` |
| Daily rate limit | `150` | `dailyLimit` | `browser.storage.local` |
| Min fetch delay | `2000` ms | `minFetchDelayMs` | `browser.storage.local` |
| Max fetch delay | `5000` ms | `maxFetchDelayMs` | `browser.storage.local` |
| Max log entries | `200` | `maxLogEntries` | `browser.storage.local` |
| Mutual page size | `10` | `mutualPageSize` | `browser.storage.local` |
| Mutual max pages | `10` | `mutualMaxPages` | `browser.storage.local` |
| URL debounce | `500` ms | `urlDebounceMs` | `browser.storage.local` |

**Constants that stay hardcoded in `constants.ts`:**

| Constant | Value | Reason |
|----------|-------|--------|
| Voyager decoration IDs | `...FullProfileWithEntities-93`, `...SearchClusterCollection-186` | Fragile LinkedIn internals — documented, not user-tunable |
| Tenant/BU/User IDs | `tenant_sys_001`, `bu_sys_001`, `usr_sys_001` | Single-user OSS, system defaults |
| Custom event names | `linkedout:*` | Internal protocol, not user-facing |
| LinkedIn API query params | `q=memberIdentity`, etc. | LinkedIn API contract, not user-tunable |
| HTTP status codes | `403`, `409`, `429` | Protocol constants |

**Complexity:** M

---

### 4H. Constants Documentation

**Goal:** Create comprehensive documentation for every externalized constant.

**Acceptance Criteria:**
- `docs/configuration.md` — complete reference guide for all configurable values
- Updated `.env.example` — all new env vars documented with comments
- Updated `config.yaml` template — all new config sections (commented out with defaults)
- Each constant documented with: name, env var, YAML key, default value, valid range/type, what it affects, and which component uses it

**File-Level Targets:**
- Create:
  - `docs/configuration.md` — full configuration reference
- Modify:
  - `backend/.env.example` — add all new env vars with documentation comments
  - Template for `~/linkedout-data/config/config.yaml` — add new sections

**Documentation Structure for `docs/configuration.md`:**

```
1. Quick Start (most common settings)
2. Core Settings (database, data dir, debug)
3. Server Settings (port, host, CORS)
4. Embedding Settings (provider, model, dimensions, batch sizes)
5. LLM Settings (provider, model, retry, timeout)
6. Enrichment Settings (Apify config, cache TTL, costs)
7. Scoring Settings (affinity weights, Dunbar tiers)
8. Logging Settings (level, rotation, retention)
9. Extension Settings (rate limits, staleness, delays)
10. Extension-Only Settings (browser.storage.local keys)
11. Constants Reference (non-configurable constants and why)
```

**Complexity:** M

---

## Testing Strategy

### Unit Tests

- **Config loading tests:** Verify that each new config field loads correctly from env vars, YAML, and defaults. Test precedence: env > YAML > default.
- **Scoring config tests:** Verify affinity scoring produces identical results when using config-loaded values vs old hardcoded values. Regression test: compute affinity for a known fixture set, compare output.
- **Enrichment config tests:** Verify Apify client uses config values for URLs, timeouts, and cost tracking.
- **Extension config tests:** Verify `getConfig()` returns defaults when storage is empty, and overrides when storage has values.

### Integration Tests

- **Backend boot test:** Backend starts successfully with only default config (no YAML, no env vars).
- **Backend boot with overrides:** Backend starts with custom config.yaml values and verifies they're applied.
- **Extension build test:** Extension builds successfully with default and custom `VITE_BACKEND_URL`.

### Verification Commands

```bash
# Verify no hardcoded constants remain in business logic (outside config module)
grep -rn "gpt-5\|gpt-4\|text-embedding" backend/src/ --include="*.py" | grep -v config.py | grep -v __pycache__
grep -rn "localhost:8001" backend/src/ --include="*.py" | grep -v config.py
grep -rn "= 1536" backend/src/ --include="*.py" | grep -v config.py | grep -v entities/

# Verify extension configurable constants are in config.ts
grep -rn "STALENESS_DAYS\|HOURLY_LIMIT\|DAILY_LIMIT" extension/lib/ --include="*.ts" | grep -v config.ts | grep -v constants.ts
```

---

## Exit Criteria Verification Checklist

- [ ] `docs/audit/backend-constants-audit.md` exists with complete inventory
- [ ] `docs/audit/extension-constants-audit.md` exists with complete inventory
- [ ] `docs/configuration.md` exists with all constants documented
- [ ] `.env.example` updated with all new env vars
- [ ] `grep -rn` for hardcoded model names in `backend/src/` (excluding `config.py`, `__pycache__`) returns zero results
- [ ] `grep -rn` for hardcoded `localhost:8001` in `backend/src/` (excluding `config.py`) returns zero results
- [ ] `grep -rn` for hardcoded embedding dimensions `= 1536` in `backend/src/` (excluding `config.py` and entity files) returns zero results
- [ ] Affinity scoring produces identical results with config-loaded defaults vs old hardcoded values
- [ ] Backend boots with default config (no custom YAML, no env vars)
- [ ] Extension `lib/config.ts` exists with typed `ExtensionConfig` and `getConfig()`
- [ ] Extension `lib/constants.ts` contains only true constants (Voyager IDs, event names, system IDs)
- [ ] All configurable extension values flow through `getConfig()`
- [ ] Log rotation settings match decision doc (50 MB rotation, 30 days retention)
- [ ] Every tunable constant has a config path documented in `docs/configuration.md`

---

## Task Execution Order

```
4A (Backend Audit) ─────┐
                        ├──► 4B (Scoring) ──┐
                        ├──► 4C (Enrichment)├──► 4E (Infrastructure) ──► 4H (Documentation)
                        ├──► 4D (LLM/Embed) ┘
4F (Extension Audit) ───┴──► 4G (Extension Extraction) ──────────────────► 4H (Documentation)
```

- **4A and 4F** can run in parallel (independent audits)
- **4B, 4C, 4D** can run in parallel after 4A (independent config domains)
- **4E** depends on 4B/4C/4D (infrastructure cleanup after domain constants are handled)
- **4G** depends on 4F (extraction after audit)
- **4H** depends on all prior tasks (documents everything)

---

## Complexity Summary

| Task | Complexity | Estimated Effort |
|------|-----------|-----------------|
| 4A. Backend constants audit | M | Audit + document |
| 4B. Backend scoring constants | M | ~8 config fields, 1 file refactor |
| 4C. Backend enrichment constants | M | ~10 config fields, 2 file refactors |
| 4D. Backend LLM & embedding constants | L | ~15 config fields, 5 file refactors, dimension validation logic |
| 4E. Backend infrastructure constants | S | ~3 config fields, 1 file fix (log rotation mismatch) |
| 4F. Extension constants audit | S | Audit + document |
| 4G. Extension constants extraction | M | New config.ts module, ~6 file updates |
| 4H. Constants documentation | M | docs/configuration.md + .env.example update |

---

## Resolved Decisions (2026-04-07, SJ)

1. **Scoring config granularity:** **Expose everything** — all weights, seniority boosts, recency thresholds, Dunbar tiers. Add thorough comments in config.yaml so users understand what each value does. Users who want to tune can tune.

2. **Embedding dimension validation:** **Detect on startup, warn loudly, suggest `linkedout embed --force`.** Wrong-dimension embeddings silently break similarity search. Must not fail silently.

3. **Extension options page timing:** **Acceptable.** No users between Phase 4 and Phase 12. Power users can edit via DevTools. Options page comes in Phase 12.

4. **Apify Actor ID:** **Keep hardcoded as a named constant** (not configurable). Include explanation comment and link to the Apify marketplace listing. Changing it breaks parsing — configurability would be a false promise.

5. **Log rotation mismatch:** **Phase 3 fixes defaults (50MB/30d), Phase 4 externalizes as config vars** (`LINKEDOUT_LOG_ROTATION_SIZE`, `LINKEDOUT_LOG_RETENTION_DAYS`). Clean separation — Phase 3 owns correctness, Phase 4 owns configurability. Phase 4 runs after Phase 3 per dependency graph.

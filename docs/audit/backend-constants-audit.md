# Backend Constants Audit

**Phase:** 4 — Constants Externalization
**Date:** 2026-04-08
**Status:** Complete

This audit catalogs every hardcoded constant in the backend codebase. Each constant includes its current value, purpose, category, and a recommendation for Phase 4.

---

## Scoring Weights

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 23 | `0.40` | Career overlap weight | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 24 | `0.25` | External contact weight | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 25 | `0.15` | Embedding similarity weight | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 26 | `0.10` | Source count weight | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 27 | `0.10` | Recency weight | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 29 | `3` | Affinity scoring version number | Scoring Weights | keep hardcoded (data-format constant, not tunable) |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 32 | `{1: 0.2, 2: 0.5, 3: 0.8}` | Source count normalization map | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 35-39 | `[(15, 'inner_circle'), (50, 'active'), (150, 'familiar')]` | Dunbar tier cutoffs (rank thresholds) | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 40 | `'acquaintance'` | Dunbar default tier | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 46-57 | `{'founder': 3.0, 'c_suite': 2.5, ...}` | Seniority boost multipliers (10 levels) | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 58 | `1.0` | Default seniority boost (unknown seniority) | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 66 | `500` | Default company size assumption when unknown | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 100-106 | `1.0, 0.7, 0.4, 0.2` (at <1y, <3y, <5y, 5y+) | Recency decay schedule | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 150 | `36.0` | Career overlap cap divisor (months) | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/scoring/affinity_scorer.py` | 178-183 | `1.0` (phone), `0.7` (email) | External contact score values | Scoring Weights | externalize |
| `backend/src/linkedout/intelligence/controllers/search_controller.py` | 42-46 | `70`, `40` | Affinity strength label thresholds (strong/moderate/weak) | Scoring Weights | externalize |

---

## Model Names

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/shared/config/settings.py` | 69 | `'gpt-5.2-2025-12-11'` | Default LLM model | Model Names | already externalized (LinkedOutSettings.llm_model) |
| `backend/src/shared/config/settings.py` | 73 | `'gpt-5.4-mini'` | Default search LLM model | Model Names | already externalized (LinkedOutSettings.search_llm_model) |
| `backend/src/utilities/llm_manager/embedding_client.py` | 22 | `'text-embedding-3-small'` | Default embedding model name | Model Names | externalize |
| `backend/src/utilities/llm_manager/embedding_client.py` | 22 | `1536` | Default embedding dimensions | Model Names | externalize |
| `backend/src/linkedout/intelligence/tools/web_tool.py` | 13 | `'gpt-4.1-mini'` | Web search tool model | Model Names | externalize |
| `backend/src/dev_tools/generate_embeddings.py` | 183, 227, 318 | `'text-embedding-3-small'` | Hardcoded in metric labels | Model Names | externalize (should read from config) |

---

## Retry / Timeout

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/shared/infra/reliability/retry_policy.py` | 17 | `3` | RetryConfig default max_attempts | Retry/Timeout | externalize |
| `backend/src/shared/infra/reliability/retry_policy.py` | 18 | `1.0` | RetryConfig default min_wait_seconds | Retry/Timeout | externalize |
| `backend/src/shared/infra/reliability/retry_policy.py` | 19 | `60.0` | RetryConfig default max_wait_seconds | Retry/Timeout | externalize |
| `backend/src/shared/infra/reliability/retry_policy.py` | 23-28 | `3, 2.0, 30.0` | LLM_RETRY_CONFIG preset | Retry/Timeout | externalize |
| `backend/src/shared/infra/reliability/retry_policy.py` | 30-35 | `3, 1.0, 15.0` | EXTERNAL_API_RETRY_CONFIG preset | Retry/Timeout | externalize |
| `backend/src/shared/infra/reliability/timeout_policy.py` | 10 | `30.0` | TimeoutConfig default timeout_seconds | Retry/Timeout | externalize |
| `backend/src/shared/infra/reliability/timeout_policy.py` | 13 | `120.0` | LLM_TIMEOUT_CONFIG | Retry/Timeout | externalize |
| `backend/src/shared/infra/reliability/timeout_policy.py` | 14 | `30.0` | EXTERNAL_API_TIMEOUT_CONFIG | Retry/Timeout | externalize |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 64 | `60` | Sync enrichment request timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 84 | `30` | Async run start request timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 89 | `300` | Poll run timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 89 | `5` | Poll run interval (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 94 | `15` | Poll status check request timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 109 | `30` | Fetch results request timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/enrichment_pipeline/controller.py` | 263 | `15` | BYOK key validation request timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/intelligence/tools/web_tool.py` | 14 | `10` | Web search tool timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/linkedout/intelligence/tools/sql_tool.py` | 15 | `10000` | SQL statement timeout (milliseconds) | Retry/Timeout | externalize |
| `backend/src/utilities/llm_manager/llm_schemas.py` | 79 | `120` | LLMConfig default timeout (seconds) | Retry/Timeout | externalize |
| `backend/src/utilities/llm_manager/llm_schemas.py` | 83 | `2` | LLMConfig default max_retries | Retry/Timeout | externalize |

---

## Rate Limits

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/shared/infra/reliability/rate_limiter.py` | 10 | `60` | Default requests per minute | Rate Limits | externalize |
| `backend/src/shared/infra/reliability/rate_limiter.py` | 11 | `100_000` | Default tokens per minute | Rate Limits | externalize |
| `backend/src/shared/config/settings.py` | 86 | `60` | LLM rate limit RPM | Rate Limits | already externalized (LinkedOutSettings.rate_limit_llm_rpm) |

---

## Cache TTLs

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/linkedout/enrichment_pipeline/controller.py` | 34 | `90` | CACHE_DAYS — enrichment cache staleness (days) | Cache TTLs | externalize (use settings.enrichment_cache_ttl_days) |
| `backend/src/linkedout/enrichment_pipeline/controller.py` | 380 | `30` | Stats period (days) — "last_30_days" | Cache TTLs | externalize |
| `backend/src/shared/config/settings.py` | 127 | `90` | enrichment_cache_ttl_days | Cache TTLs | already externalized |
| `backend/src/shared/config/settings.py` | 77 | `300` | Prompt cache TTL (seconds) | Cache TTLs | already externalized |

---

## API URLs

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 18 | `'https://api.apify.com/v2'` | Apify base API URL | API URLs | externalize |
| `backend/src/linkedout/enrichment_pipeline/controller.py` | 262 | `'https://api.apify.com/v2/users/me'` | Apify key validation URL (derived from base) | API URLs | defer (derive from externalized base URL) |
| `backend/src/dev_tools/wikidata_utils.py` | 15 | `'https://www.wikidata.org/w/api.php'` | Wikidata search API | API URLs | defer (dev tools only) |
| `backend/src/dev_tools/wikidata_utils.py` | 16 | `'https://query.wikidata.org/sparql'` | Wikidata SPARQL endpoint | API URLs | defer (dev tools only) |
| `backend/src/dev_tools/seed_companies.py` | 25 | `'https://yc-oss.github.io/api/companies/all.json'` | YC companies API URL | API URLs | defer (dev tools only) |

---

## Batch Sizes

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/dev_tools/generate_embeddings.py` | 48 | `5000` | Experience pre-load SQL chunk size | Batch Sizes | externalize |
| `backend/src/dev_tools/generate_embeddings.py` | 95 | `500` | DB write batch size for embedding updates | Batch Sizes | externalize |
| `backend/src/dev_tools/generate_embeddings.py` | 138 | `500` | CLI default chunk size (--chunk-size flag) | Batch Sizes | already externalized (CLI flag) |
| `backend/src/utilities/llm_manager/embedding_client.py` | 106 | `'24h'` | Batch API completion window | Batch Sizes | keep hardcoded (OpenAI API constraint) |
| `backend/src/utilities/llm_manager/embedding_client.py` | 110 | `30` | Batch poll interval (seconds) | Batch Sizes | externalize |
| `backend/src/utilities/llm_manager/embedding_client.py` | 110 | `3600` | Batch poll timeout (seconds) | Batch Sizes | externalize |
| `backend/src/linkedout/intelligence/explainer/why_this_person.py` | 25 | `10` | Explanation batch size (profiles per LLM call) | Batch Sizes | externalize |
| `backend/src/dev_tools/wikidata_utils.py` | 89 | `80` | SPARQL batch size | Batch Sizes | defer (dev tools only) |
| `backend/src/dev_tools/classify_roles.py` | 95 | `500` | Role classification DB batch size | Batch Sizes | defer (dev tools only) |
| `backend/src/dev_tools/enrich_companies.py` | 481 | `500` | Company enrichment DB batch size | Batch Sizes | defer (dev tools only) |

---

## Server Config

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/shared/config/settings.py` | 50 | `'postgresql://linkedout:@localhost:5432/linkedout'` | Default database URL | DB Settings | already externalized (LinkedOutSettings.database_url) |
| `backend/src/shared/config/settings.py` | 53 | `'~/linkedout-data'` | Default data directory | Server Config | already externalized (LinkedOutSettings.data_dir) |
| `backend/src/shared/config/settings.py` | 54 | `'local'` | Default environment name | Server Config | already externalized (LinkedOutSettings.environment) |
| `backend/src/shared/config/settings.py` | 58 | `'localhost'` | Default backend host | Server Config | already externalized (LinkedOutSettings.backend_host) |
| `backend/src/shared/config/settings.py` | 59 | `8001` | Default backend port | Server Config | already externalized (LinkedOutSettings.backend_port) |
| `backend/src/shared/auth/config.py` | 22 | `'dev@localhost'` | Dev bypass user email | Server Config | keep hardcoded (dev-only constant) |
| `backend/main.py` | 159 | `'1.0.0'` | API version string | Server Config | keep hardcoded |

---

## LLM Settings

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/utilities/llm_manager/llm_schemas.py` | 71 | `0.7` | Default LLM temperature | LLM Settings | externalize |
| `backend/src/shared/config/settings.py` | 74 | `4` | Summarize beyond N turns threshold | LLM Settings | already externalized |
| `backend/src/shared/config/settings.py` | 76 | `False` | Load prompts from local file | LLM Settings | already externalized |

---

## Magic Numbers (Intelligence Layer)

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/linkedout/intelligence/controllers/_sse_helpers.py` | 18 | `15` | SSE heartbeat interval (seconds) | Magic Numbers | externalize |
| `backend/src/linkedout/intelligence/agents/search_agent.py` | 47 | `20` | Max agent iterations per turn | Magic Numbers | externalize |
| `backend/src/linkedout/intelligence/services/best_hop_service.py` | 22 | `50` | Max mutuals for experience lookup | Magic Numbers | externalize |
| `backend/src/linkedout/intelligence/tools/web_tool.py` | 15 | `3` | Max web searches per turn | Magic Numbers | externalize |
| `backend/src/linkedout/intelligence/tools/sql_tool.py` | 14 | `100` | Max SQL result rows | Magic Numbers | externalize |
| `backend/src/linkedout/intelligence/tools/vector_tool.py` | 40 | `20` | Default vector search result limit | Magic Numbers | externalize |
| `backend/src/linkedout/intelligence/agents/search_agent.py` | 729 | `20` | Default search result limit | Magic Numbers | externalize |

---

## Cost Tracking

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 19 | `0.004` | Cost per profile in USD | Cost Tracking | externalize |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 20 | `'Profile details no email ($4 per 1k)'` | Apify actor scraper mode string | Cost Tracking | keep hardcoded (Apify-specific parameter) |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 17 | `'LpVuK3Zozwuipa5bp'` | Apify Actor ID for LinkedIn scraper | Cost Tracking | keep hardcoded (per constraint — changing breaks response parsing) |

---

## ID Prefixes / Nanoids

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/shared/common/nanoids.py` | 23 | `21` | Standard nanoid size (characters) | ID Prefixes | keep hardcoded (data-format constant) |
| `backend/src/shared/common/nanoids.py` | 36 | `21` | Prefixed nanoid size (characters) | ID Prefixes | keep hardcoded (data-format constant) |
| `backend/src/shared/common/nanoids.py` | 50 | `8` | Timestamped ID suffix size | ID Prefixes | keep hardcoded (data-format constant) |
| `backend/src/shared/utilities/correlation.py` | 35 | `12` | Correlation ID suffix size | ID Prefixes | keep hardcoded (not user-tunable) |

---

## Log Settings

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/shared/utilities/logger.py` | 76 | `'50 MB'` | Log rotation size default | Log Settings | already externalized (LINKEDOUT_LOG_ROTATION env var) |
| `backend/src/shared/utilities/logger.py` | 77 | `'30 days'` | Log retention period default | Log Settings | already externalized (LINKEDOUT_LOG_RETENTION env var) |
| `backend/src/shared/utilities/logger.py` | 32 | `6` | Stdlib intercept stack depth | Log Settings | keep hardcoded (implementation detail) |
| `backend/src/shared/utilities/logger.py` | 39-46 | `{'backend': 'backend.log', ...}` | Component log file name map | Log Settings | keep hardcoded (structural constant) |

---

## System IDs (Single-User OSS)

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/dev_tools/db/fixed_data.py` | 219 | `'tenant_sys_001'` | System tenant ID | System IDs | keep hardcoded (per constraint — single-user OSS) |
| `backend/src/dev_tools/db/fixed_data.py` | 224 | `'bu_sys_001'` | System BU ID | System IDs | keep hardcoded (per constraint) |
| `backend/src/dev_tools/db/fixed_data.py` | 229 | `'usr_sys_001'` | System user ID | System IDs | keep hardcoded (per constraint) |

---

## Dev Tools Only (deferred)

| File | Line | Value | Description | Category | Recommendation |
|------|------|-------|-------------|----------|----------------|
| `backend/src/dev_tools/wikidata_utils.py` | 18 | `0.3` | Wikidata search delay (seconds) | Rate Limits | defer |
| `backend/src/dev_tools/wikidata_utils.py` | 20 | `'LinkedOut/1.0 (https://github.com/linkedout-oss/linkedout)'` | HTTP User-Agent string | API URLs | defer |
| `backend/src/dev_tools/wikidata_utils.py` | 36 | `5` | Wikidata search result limit | Batch Sizes | defer |
| `backend/src/dev_tools/download_profile_pics.py` | 23 | `10` | Max concurrent downloads | Batch Sizes | defer |
| `backend/src/dev_tools/reconcile_stubs.py` | 30 | `3` | Minimum first name length | Magic Numbers | defer |
| `backend/src/dev_tools/seed_companies.py` | 26 | Path to PDL CSV | Filesystem path constant | Server Config | defer |

---

## Summary

### By Category

| Category | Count |
|----------|-------|
| Scoring Weights | 16 |
| Retry/Timeout | 19 |
| Model Names | 6 |
| Rate Limits | 3 |
| Cache TTLs | 4 |
| API URLs | 5 |
| Batch Sizes | 10 |
| Server Config | 7 |
| LLM Settings | 3 |
| Magic Numbers (Intelligence) | 7 |
| Cost Tracking | 3 |
| ID Prefixes / Nanoids | 4 |
| Log Settings | 4 |
| System IDs | 3 |
| Dev Tools (deferred) | 6 |
| **Total** | **100** |

### By Recommendation

| Recommendation | Count |
|----------------|-------|
| externalize | 60 |
| already externalized | 16 |
| keep hardcoded | 15 |
| defer (dev tools / derived) | 9 |
| **Total** | **100** |

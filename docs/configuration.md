# LinkedOut Configuration Reference

LinkedOut uses a three-layer configuration hierarchy. Values are resolved in this order (highest priority wins):

1. **Environment variables** — `LINKEDOUT_` prefix, or industry-standard names
2. **`~/linkedout-data/config/config.yaml`** — human-readable YAML
3. **`~/linkedout-data/config/secrets.yaml`** — API keys, `chmod 600`
4. **Code defaults** — in the `LinkedOutSettings` pydantic-settings class

For nested config sections (scoring, enrichment, llm, embedding), use double-underscore `__` for env var overrides:
```
LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP=0.35
```

See also: `docs/decision/env-config-design.md` for the full design rationale.

---

## 1. Quick Start

Most users only need to set a few values. The `/linkedout-setup` command generates these automatically.

### Minimum viable config (`~/linkedout-data/config/config.yaml`)

```yaml
database_url: postgresql://linkedout:YOUR_PASSWORD@localhost:5432/linkedout
```

### Minimum viable secrets (`~/linkedout-data/config/secrets.yaml`)

```yaml
openai_api_key: sk-...
```

### Common customizations

```bash
# Change the backend port
export LINKEDOUT_BACKEND_PORT=9000

# Use local embeddings instead of OpenAI
export LINKEDOUT_EMBEDDING__PROVIDER=local

# Increase log verbosity
export LINKEDOUT_LOG_LEVEL=DEBUG

# Tune scoring weights
export LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP=0.50
```

---

## 2. Core Settings

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `database_url` | `DATABASE_URL` | `postgresql://linkedout:@localhost:5432/linkedout` | string | PostgreSQL connection string. Must start with `postgresql://` or `postgres://`. | backend |
| `data_dir` | `LINKEDOUT_DATA_DIR` | `~/linkedout-data` | string (path) | Root directory for all config, data, logs. `~` is expanded. | backend |
| `environment` | `LINKEDOUT_ENVIRONMENT` | `local` | string | Environment name: `local`, `test`, `prod`. Affects behavior, not file selection. | backend |
| `debug` | `LINKEDOUT_DEBUG` | `false` | bool | Debug mode — verbose output and stack traces. | backend |

---

## 3. Server Settings

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `backend_host` | `LINKEDOUT_BACKEND_HOST` | `localhost` | string | Backend bind host. | backend |
| `backend_port` | `LINKEDOUT_BACKEND_PORT` | `8001` | int (1-65535) | Backend bind port. | backend |
| `backend_url` | `LINKEDOUT_BACKEND_URL` | (computed) | string | Full backend URL. Computed from `http://{host}:{port}` if not set. | backend |
| `cors_origins` | `LINKEDOUT_CORS_ORIGINS` | (empty) | string | Comma-separated allowed CORS origins. | backend |

---

## 4. Embedding Settings

Nested under `embedding` in YAML. Env var prefix: `LINKEDOUT_EMBEDDING__`.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `embedding.provider` | `LINKEDOUT_EMBEDDING__PROVIDER` | `openai` | string | Embedding provider: `openai` or `local` (nomic-embed-text-v1.5). | backend |
| `embedding.model` | `LINKEDOUT_EMBEDDING__MODEL` | `text-embedding-3-small` | string | Embedding model name. Provider defaults: OpenAI=`text-embedding-3-small`, local=`nomic-embed-text-v1.5`. | backend |
| `embedding.dimensions` | `LINKEDOUT_EMBEDDING__DIMENSIONS` | `1536` | int | Embedding vector dimensions. Expected: 1536 (OpenAI), 768 (local/nomic). A mismatch triggers a startup warning. | backend |
| `embedding.chunk_size` | `LINKEDOUT_EMBEDDING__CHUNK_SIZE` | `5000` | int | Number of records per embedding batch. | backend |
| `embedding.batch_timeout_seconds` | `LINKEDOUT_EMBEDDING__BATCH_TIMEOUT_SECONDS` | `7200` | int | Maximum wait time for batch embedding jobs (seconds). | backend |
| `embedding.batch_poll_interval_seconds` | `LINKEDOUT_EMBEDDING__BATCH_POLL_INTERVAL_SECONDS` | `30` | int | Poll interval for batch embedding job status (seconds). | backend |

**Dimension validation:** On startup, LinkedOut checks if the configured dimensions match the expected dimensions for the selected provider. If mismatched, it logs a warning suggesting `linkedout embed --force` to re-embed. Wrong dimensions silently break similarity search.

---

## 5. LLM Settings

Nested under `llm` in YAML. Env var prefix: `LINKEDOUT_LLM__`.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `llm.provider` | `LINKEDOUT_LLM__PROVIDER` | `openai` | string | LLM provider for enrichment and search. | backend |
| `llm.model` | `LINKEDOUT_LLM__MODEL` | `gpt-5.2-2025-12-11` | string | Primary LLM model for analysis and enrichment. | backend |
| `llm.search_model` | `LINKEDOUT_LLM__SEARCH_MODEL` | `gpt-5.4-mini` | string | Lightweight model for search agent operations. | backend |
| `llm.timeout_seconds` | `LINKEDOUT_LLM__TIMEOUT_SECONDS` | `120.0` | float | LLM request timeout (seconds). | backend |
| `llm.retry_max_attempts` | `LINKEDOUT_LLM__RETRY_MAX_ATTEMPTS` | `3` | int | Max retry attempts for failed LLM calls. | backend |
| `llm.retry_min_wait` | `LINKEDOUT_LLM__RETRY_MIN_WAIT` | `2.0` | float | Minimum wait between LLM retries (seconds). | backend |
| `llm.retry_max_wait` | `LINKEDOUT_LLM__RETRY_MAX_WAIT` | `30.0` | float | Maximum wait between LLM retries (seconds). | backend |
| `llm.rate_limit_rpm` | `LINKEDOUT_LLM__RATE_LIMIT_RPM` | `60` | int | LLM requests per minute rate limit. | backend |
| `llm.prompt_cache_ttl_seconds` | `LINKEDOUT_LLM__PROMPT_CACHE_TTL_SECONDS` | `300` | int | Prompt template cache TTL (seconds). | backend |
| `llm.summarize_beyond_n_turns` | `LINKEDOUT_LLM__SUMMARIZE_BEYOND_N_TURNS` | `4` | int | Number of conversation turns before auto-summarization. | backend |

---

## 6. Enrichment Settings

Nested under `enrichment` in YAML. Env var prefix: `LINKEDOUT_ENRICHMENT__`.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `enrichment.apify_base_url` | `LINKEDOUT_ENRICHMENT__APIFY_BASE_URL` | `https://api.apify.com/v2` | string | Apify API base URL. | backend |
| `enrichment.cost_per_profile_usd` | `LINKEDOUT_ENRICHMENT__COST_PER_PROFILE_USD` | `0.004` | float | Cost tracking: USD per enriched profile ($4 per 1k). | backend |
| `enrichment.cache_ttl_days` | `LINKEDOUT_ENRICHMENT__CACHE_TTL_DAYS` | `90` | int | Days before a cached enrichment result is considered stale. | backend |
| `enrichment.sync_timeout_seconds` | `LINKEDOUT_ENRICHMENT__SYNC_TIMEOUT_SECONDS` | `60` | int | Timeout for synchronous enrichment requests (seconds). | backend |
| `enrichment.async_start_timeout_seconds` | `LINKEDOUT_ENRICHMENT__ASYNC_START_TIMEOUT_SECONDS` | `30` | int | Timeout for starting an async enrichment run (seconds). | backend |
| `enrichment.run_poll_timeout_seconds` | `LINKEDOUT_ENRICHMENT__RUN_POLL_TIMEOUT_SECONDS` | `300` | int | Max time to poll an enrichment run for completion (seconds). | backend |
| `enrichment.run_poll_interval_seconds` | `LINKEDOUT_ENRICHMENT__RUN_POLL_INTERVAL_SECONDS` | `5` | int | Interval between enrichment run status checks (seconds). | backend |
| `enrichment.fetch_results_timeout_seconds` | `LINKEDOUT_ENRICHMENT__FETCH_RESULTS_TIMEOUT_SECONDS` | `30` | int | Timeout for fetching enrichment results (seconds). | backend |
| `enrichment.key_validation_timeout_seconds` | `LINKEDOUT_ENRICHMENT__KEY_VALIDATION_TIMEOUT_SECONDS` | `15` | int | Timeout for Apify API key validation (seconds). | backend |

---

## 7. Scoring Settings

Nested under `scoring` in YAML. Env var prefix: `LINKEDOUT_SCORING__`.

These weights control the affinity scoring algorithm that ranks your professional connections.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `scoring.weight_career_overlap` | `LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP` | `0.40` | float | Weight for shared work history in affinity score. | backend |
| `scoring.weight_external_contact` | `LINKEDOUT_SCORING__WEIGHT_EXTERNAL_CONTACT` | `0.25` | float | Weight for having phone/email contact info. | backend |
| `scoring.weight_embedding_similarity` | `LINKEDOUT_SCORING__WEIGHT_EMBEDDING_SIMILARITY` | `0.15` | float | Weight for semantic similarity of career trajectories. | backend |
| `scoring.weight_source_count` | `LINKEDOUT_SCORING__WEIGHT_SOURCE_COUNT` | `0.10` | float | Weight for number of data sources confirming the connection. | backend |
| `scoring.weight_recency` | `LINKEDOUT_SCORING__WEIGHT_RECENCY` | `0.10` | float | Weight for how recently you interacted or overlapped. | backend |
| `scoring.dunbar_inner_circle` | `LINKEDOUT_SCORING__DUNBAR_INNER_CIRCLE` | `15` | int | Rank cutoff for "inner circle" Dunbar tier. | backend |
| `scoring.dunbar_active` | `LINKEDOUT_SCORING__DUNBAR_ACTIVE` | `50` | int | Rank cutoff for "active" Dunbar tier. | backend |
| `scoring.dunbar_familiar` | `LINKEDOUT_SCORING__DUNBAR_FAMILIAR` | `150` | int | Rank cutoff for "familiar" Dunbar tier. Connections ranked above this are "acquaintance". | backend |
| `scoring.seniority_boosts` | `LINKEDOUT_SCORING__SENIORITY_BOOSTS` | `{"founder": 3.0, "c_suite": 2.5, ...}` | dict[str, float] | Multiplier applied to affinity score based on contact's seniority level. 10 levels: founder (3.0), c_suite (2.5), vp (2.0), director (1.8), manager (1.5), lead (1.3), senior (1.1), mid (1.0), junior (0.9), intern (0.7). | backend |
| `scoring.external_contact_scores` | `LINKEDOUT_SCORING__EXTERNAL_CONTACT_SCORES` | `{"phone": 1.0, "email": 0.7}` | dict[str, float] | Score value for each type of external contact info. | backend |
| `scoring.career_normalization_months` | `LINKEDOUT_SCORING__CAREER_NORMALIZATION_MONTHS` | `36` | int | Career overlap is normalized by dividing by this many months. | backend |
| `scoring.recency_thresholds` | `LINKEDOUT_SCORING__RECENCY_THRESHOLDS` | `[[12, 1.0], [36, 0.7], [60, 0.4]]` | list[list] | Recency decay schedule: `[months, score]` pairs. Connections older than all thresholds score 0.2. | backend |

**How scoring works:** The affinity score is `sum(weight_i * signal_i)` where signal values are normalized 0-1. The five weights should sum to 1.0. The Dunbar tiers assign labels (inner_circle, active, familiar, acquaintance) based on rank position. Seniority boosts are multiplied on top of the base score.

---

## 8. Logging Settings

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `log_level` | `LINKEDOUT_LOG_LEVEL` | `INFO` | string | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. | backend |
| `log_format` | `LINKEDOUT_LOG_FORMAT` | `human` | string | Log format: `human` (colorized, readable) or `json` (structured). | backend |
| `log_dir` | `LINKEDOUT_LOG_DIR` | `~/linkedout-data/logs` | string (path) | Log file directory. Defaults to `{data_dir}/logs`. | backend |
| `log_rotation` | `LINKEDOUT_LOG_ROTATION` | `50 MB` | string | Log file rotation size. Loguru format (e.g., `50 MB`, `100 MB`). | backend |
| `log_retention` | `LINKEDOUT_LOG_RETENTION` | `30 days` | string | Log file retention period. Loguru format (e.g., `30 days`, `7 days`). | backend |
| `metrics_dir` | `LINKEDOUT_METRICS_DIR` | `~/linkedout-data/metrics` | string (path) | Metrics directory. Defaults to `{data_dir}/metrics`. | backend |
| `db_echo_log` | `LINKEDOUT_DB_ECHO_LOG` | `false` | bool | Echo all SQL queries to log (SQLAlchemy engine echo). Very verbose. | backend |

**Per-module overrides:** Set `LOG_LEVEL_<MODULE>=LEVEL` to override log level for specific modules (e.g., `LOG_LEVEL_CLI_IMPORT=DEBUG`). Module names use underscore format with prefix matching.

---

## 9. External API Defaults

Nested under `external_api` in YAML. Env var prefix: `LINKEDOUT_EXTERNAL_API__`.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `external_api.retry_max_attempts` | `LINKEDOUT_EXTERNAL_API__RETRY_MAX_ATTEMPTS` | `3` | int | Default max retry attempts for external API calls. | backend |
| `external_api.timeout_seconds` | `LINKEDOUT_EXTERNAL_API__TIMEOUT_SECONDS` | `30.0` | float | Default timeout for external API calls (seconds). | backend |

---

## 10. Pagination

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `default_page_size` | `LINKEDOUT_DEFAULT_PAGE_SIZE` | `20` | int | Default number of results per page in API list endpoints. | backend |

---

## 11. API Keys

These use industry-standard names (no `LINKEDOUT_` prefix). Store in `~/linkedout-data/config/secrets.yaml` or as env vars.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `openai_api_key` | `OPENAI_API_KEY` | (none) | string | OpenAI API key. Required when `embedding.provider=openai`. | backend |
| `apify_api_key` | `APIFY_API_KEY` | (none) | string | Apify API key. Required only for extension enrichment (profile lookup). | backend |

---

## 12. Observability (Langfuse)

Optional LLM observability integration. Off by default.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `langfuse_enabled` | `LANGFUSE_ENABLED` | `false` | bool | Enable Langfuse LLM tracing. | backend |
| `langfuse_public_key` | `LANGFUSE_PUBLIC_KEY` | (none) | string | Langfuse public key. Required if enabled. | backend |
| `langfuse_secret_key` | `LANGFUSE_SECRET_KEY` | (none) | string | Langfuse secret key. Required if enabled. | backend |
| `langfuse_host` | `LANGFUSE_HOST` | (none) | string | Langfuse host URL. Required if enabled. | backend |

---

## 13. Extension Tuning

These backend settings affect extension behavior. They're also available in the extension's runtime config.

| Config Key (YAML) | Env Var | Default | Type | Description | Component |
|---|---|---|---|---|---|
| `rate_limit_hourly` | `LINKEDOUT_RATE_LIMIT_HOURLY` | `30` | int | Max Voyager profile fetches per hour. | backend + extension |
| `rate_limit_daily` | `LINKEDOUT_RATE_LIMIT_DAILY` | `150` | int | Max Voyager profile fetches per day. | backend + extension |
| `staleness_days` | `LINKEDOUT_STALENESS_DAYS` | `30` | int | Days after which a cached profile is considered stale and re-fetched. | backend + extension |
| `enrichment_cache_ttl_days` | `LINKEDOUT_ENRICHMENT_CACHE_TTL_DAYS` | `90` | int | Enrichment cache lifetime (days). | backend |

---

## 14. Extension Settings (browser.storage.local)

The Chrome extension has its own runtime config stored in `browser.storage.local` under the `linkedout_config` key. These values can be edited via Chrome DevTools (Phase 12 will add an options page).

**To edit via DevTools:**
1. Open `chrome://extensions`, find LinkedOut, click "Inspect views: background"
2. In the console, run:
   ```javascript
   chrome.storage.local.get('linkedout_config', console.log)  // read
   chrome.storage.local.set({ linkedout_config: { hourlyLimit: 50 } })  // update
   ```

| Config Key | Default | Type | Description |
|---|---|---|---|
| `backendUrl` | `http://localhost:8001` | string | Backend API URL. Build-time: `VITE_BACKEND_URL`. |
| `stalenessDays` | `30` | number | Profile staleness threshold (days). |
| `hourlyLimit` | `30` | number | Max Voyager fetches per hour. |
| `dailyLimit` | `150` | number | Max Voyager fetches per day. |
| `minFetchDelayMs` | `2000` | number | Minimum random delay between page fetches (ms). |
| `maxFetchDelayMs` | `5000` | number | Maximum random delay between page fetches (ms). |
| `maxLogEntries` | `200` | number | Max activity log entries in storage. |
| `mutualMaxPages` | `10` | number | Max pages to scrape for mutual connections. |
| `urlDebounceMs` | `500` | number | Debounce timer for SPA navigation detection (ms). |
| `recentActivityLimit` | `20` | number | Default limit for recent activity queries. |
| `mutualFirstPageDelayBaseMs` | `1000` | number | Base delay before first mutual connection page fetch (ms). |
| `mutualFirstPageDelayRangeMs` | `1500` | number | Random range added to first page delay (ms). |

### Build-time Extension Config

| Env Var | Default | Description |
|---|---|---|
| `VITE_BACKEND_URL` | `http://localhost:8001` | Backend URL baked into the extension at build time. Users running on a different port must rebuild or override via storage. |

---

## 15. Constants Reference (Non-Configurable)

These values are intentionally **not** configurable. Changing them would break functionality or data integrity.

### Apify Actor ID

- **Value:** `LpVuK3Zozwuipa5bp`
- **File:** `backend/src/linkedout/enrichment_pipeline/apify_client.py`
- **Why not configurable:** This identifies the specific Apify actor (LinkedIn profile scraper). The response format is tightly coupled to this actor. Changing the ID would break response parsing. See the [Apify marketplace listing](https://apify.com/store) for details.

### Apify Scraper Mode

- **Value:** `'Profile details no email ($4 per 1k)'`
- **File:** `backend/src/linkedout/enrichment_pipeline/apify_client.py`
- **Why not configurable:** Coupled to the Apify actor's behavior and response format.

### Nanoid Sizes

- **Values:** 21 (standard), 21 (prefixed), 8 (timestamped suffix), 12 (correlation ID suffix)
- **File:** `backend/src/shared/common/nanoids.py`, `backend/src/shared/utilities/correlation.py`
- **Why not configurable:** Data-format constants. Changing them would make existing IDs incompatible.

### Entity ID Prefixes

- **Values:** `conn_`, `comp_`, `exp_`, `edu_`, etc.
- **File:** Each entity class defines `id_prefix` on `BaseEntity`
- **Why not configurable:** Data-format constants. Existing database records use these prefixes for identification.

### Voyager Decoration IDs

- **Values:** `FullProfileWithEntities-93`, `SearchClusterCollection-186`
- **File:** `extension/lib/constants.ts`
- **Why not configurable:** LinkedIn internal API identifiers. They are **fragile** and may change when LinkedIn updates their API. Wrong values cause 400 errors or empty results. They must match LinkedIn's current API exactly. When breakage occurs, update the values in `constants.ts`.

### Mutual Connection Page Size

- **Value:** `10`
- **File:** `extension/lib/constants.ts`
- **Why not configurable:** Must match LinkedIn's Voyager search pagination size.

### System IDs (Single-User OSS)

- **Values:** `tenant_sys_001`, `bu_sys_001`, `usr_sys_001`
- **Files:** `backend/src/dev_tools/db/fixed_data.py`, `extension/lib/constants.ts`
- **Why not configurable:** Single-user OSS uses fixed system defaults for tenant, business unit, and user. Multi-tenancy is not supported in the OSS version.

### Affinity Scoring Version

- **Value:** `3`
- **File:** `backend/src/linkedout/intelligence/scoring/affinity_scorer.py`
- **Why not configurable:** Data-format constant. Stored alongside scores to track which algorithm version produced them.

### pgvector Embedding Dimension (Schema)

- **Value:** `1536`
- **Where:** PostgreSQL column definition (`Vector(1536)`)
- **Why not configurable at runtime:** Changing the vector dimension requires a database migration (`ALTER TABLE ... ALTER COLUMN`). The config value `embedding.dimensions` should match the schema. If you change embedding providers/models, run `linkedout embed --force` after migrating the schema.

---

## Complete `config.yaml` Template

This template shows all available settings with their defaults. Uncommented lines are the most commonly changed values. All other lines are commented out — uncomment to override defaults.

```yaml
# LinkedOut Configuration
# Env vars override any value here. See: docs/configuration.md

# ── Database ─────────────────────────────────────────────
database_url: postgresql://linkedout:YOUR_PASSWORD@localhost:5432/linkedout

# ── Core ─────────────────────────────────────────────────
# data_dir: ~/linkedout-data
# environment: local           # local | test | prod
# debug: false

# ── Server ───────────────────────────────────────────────
# backend_host: localhost
# backend_port: 8001
# backend_url:                 # computed from host+port if empty
# cors_origins:                # comma-separated origins

# ── Embeddings ───────────────────────────────────────────
embedding:
  provider: openai             # openai | local
  # model: text-embedding-3-small
  # dimensions: 1536           # 1536 for OpenAI, 768 for local/nomic
  # chunk_size: 5000
  # batch_timeout_seconds: 7200
  # batch_poll_interval_seconds: 30

# ── LLM ──────────────────────────────────────────────────
llm:
  # provider: openai
  # model: gpt-5.2-2025-12-11
  # search_model: gpt-5.4-mini
  # timeout_seconds: 120.0
  # retry_max_attempts: 3
  # retry_min_wait: 2.0
  # retry_max_wait: 30.0
  # rate_limit_rpm: 60
  # prompt_cache_ttl_seconds: 300
  # summarize_beyond_n_turns: 4

# ── Enrichment (Apify) ──────────────────────────────────
enrichment:
  # apify_base_url: https://api.apify.com/v2
  # cost_per_profile_usd: 0.004
  # cache_ttl_days: 90
  # sync_timeout_seconds: 60
  # async_start_timeout_seconds: 30
  # run_poll_timeout_seconds: 300
  # run_poll_interval_seconds: 5
  # fetch_results_timeout_seconds: 30
  # key_validation_timeout_seconds: 15

# ── Scoring ──────────────────────────────────────────────
scoring:
  # weight_career_overlap: 0.40
  # weight_external_contact: 0.25
  # weight_embedding_similarity: 0.15
  # weight_source_count: 0.10
  # weight_recency: 0.10
  # dunbar_inner_circle: 15
  # dunbar_active: 50
  # dunbar_familiar: 150
  # career_normalization_months: 36
  # recency_thresholds:
  #   - [12, 1.0]
  #   - [36, 0.7]
  #   - [60, 0.4]

# ── External API Defaults ────────────────────────────────
external_api:
  # retry_max_attempts: 3
  # timeout_seconds: 30.0

# ── Logging ──────────────────────────────────────────────
log_level: INFO                # DEBUG | INFO | WARNING | ERROR
# log_format: human            # human | json
# log_dir:                     # defaults to {data_dir}/logs
# log_rotation: 50 MB
# log_retention: 30 days
# metrics_dir:                 # defaults to {data_dir}/metrics
# db_echo_log: false

# ── Pagination ───────────────────────────────────────────
# default_page_size: 20

# ── Extension Tuning ─────────────────────────────────────
# rate_limit_hourly: 30
# rate_limit_daily: 150
# staleness_days: 30
# enrichment_cache_ttl_days: 90

# ── Observability (off by default) ───────────────────────
# langfuse_enabled: false
# langfuse_public_key:
# langfuse_secret_key:
# langfuse_host:
```

---

## For CI and Automation

In CI pipelines, test environments, or automation scripts, use environment variables with the `LINKEDOUT_` prefix instead of YAML files. Every config value can be set via env var.

### Env var naming convention

- LinkedOut-specific settings: `LINKEDOUT_` + `UPPER_SNAKE_CASE` (e.g., `LINKEDOUT_LOG_LEVEL`)
- Nested settings: double underscore `__` separator (e.g., `LINKEDOUT_EMBEDDING__PROVIDER`)
- Industry-standard vars: use their standard names — `DATABASE_URL`, `OPENAI_API_KEY`

### Example: CI environment

```bash
export DATABASE_URL=postgresql://linkedout:test@localhost:5432/linkedout_test
export LINKEDOUT_ENVIRONMENT=test
export LINKEDOUT_DATA_DIR=/tmp/linkedout-test-data
export LINKEDOUT_LOG_LEVEL=WARNING
export LINKEDOUT_EMBEDDING__PROVIDER=local
```

### Example: switch embedding provider

```bash
# Use free local embeddings (slower, ~275MB model download)
export LINKEDOUT_EMBEDDING__PROVIDER=local

# Use OpenAI embeddings (faster, requires API key)
export LINKEDOUT_EMBEDDING__PROVIDER=openai
export OPENAI_API_KEY=sk-...
```

### Example: custom data directory

```bash
export LINKEDOUT_DATA_DIR=/opt/linkedout/data
```

All subdirectories (config, logs, metrics, reports, seed) are created automatically under this root.

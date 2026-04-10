# SP3: Backend Enrichment Constants Extraction

**Sub-phase:** 3 of 7
**Plan task:** 4C (Backend Enrichment Constants Extraction)
**Dependencies:** SP2 (config.py has been modified — build on it)
**Estimated complexity:** M
**Changes code:** Yes

---

## Objective

Move all enrichment-related constants (Apify settings, cache TTLs, timeouts, costs) from scattered inline values in `apify_client.py` and `controller.py` into the config system via a nested `EnrichmentConfig` pydantic model.

---

## Steps

### 1. Create `EnrichmentConfig` nested model in config.py

Add a new `EnrichmentConfig(BaseModel)` class in `backend/src/shared/config/config.py`. Add an `enrichment: EnrichmentConfig = EnrichmentConfig()` field to `LinkedOutSettings`.

**Constants to add:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `apify_base_url` | `str` | `https://api.apify.com/v2` | Apify API base URL |
| `cost_per_profile_usd` | `float` | `0.004` | Apify cost per profile lookup |
| `cache_ttl_days` | `int` | `90` | Enrichment cache lifetime in days |
| `sync_timeout_seconds` | `int` | `60` | Sync enrichment timeout |
| `async_start_timeout_seconds` | `int` | `30` | Async enrichment start timeout |
| `run_poll_timeout_seconds` | `int` | `300` | Apify run poll timeout |
| `run_poll_interval_seconds` | `int` | `5` | Apify run poll interval |
| `fetch_results_timeout_seconds` | `int` | `30` | Fetch enrichment results timeout |
| `key_validation_timeout_seconds` | `int` | `15` | API key validation timeout |

**NOT configurable — stays as a named constant:**
- `APIFY_LINKEDIN_ACTOR_ID = "LpVuK3Zozwuipa5bp"` — keep in `apify_client.py` with an explanation comment:
  ```python
  # This Actor ID is coupled to the response schema we parse.
  # Changing it will break enrichment result parsing.
  # See: https://apify.com/capademir/linkedin-profile-scraper
  APIFY_LINKEDIN_ACTOR_ID = "LpVuK3Zozwuipa5bp"
  ```

### 2. Update `apify_client.py` to read from config

In `backend/src/linkedout/enrichment_pipeline/apify_client.py`:
- Remove hardcoded `BASE_URL`, `COST_PER_PROFILE_USD`, `ACTOR_SCRAPER_MODE`, and all inline timeout values
- Keep `APIFY_LINKEDIN_ACTOR_ID` as a named constant with explanation comment
- Read all configurable values from `EnrichmentConfig` via settings

### 3. Update `controller.py` to read from config

In `backend/src/linkedout/enrichment_pipeline/controller.py`:
- Replace `CACHE_DAYS` (90) with config read
- Replace inline Apify validation URL with config-derived URL
- Replace timeout (15s) with config read

### 4. Add enrichment section to config.yaml template

```yaml
# ── Enrichment (Apify Profile Lookup) ────────────────────
# enrichment:
#   apify_base_url: https://api.apify.com/v2  # Apify API endpoint
#   cost_per_profile_usd: 0.004               # Cost tracking per profile
#   cache_ttl_days: 90                         # Days before re-enriching a profile
#   sync_timeout_seconds: 60                   # Timeout for sync enrichment
#   run_poll_timeout_seconds: 300              # Timeout waiting for Apify run
#   run_poll_interval_seconds: 5               # Poll interval for Apify run status
```

---

## Verification

- [ ] `EnrichmentConfig` model exists in `config.py` with all fields listed above
- [ ] `LinkedOutSettings` has an `enrichment: EnrichmentConfig` field
- [ ] `apify_client.py` reads all configurable values from config (no hardcoded URLs, timeouts, or costs except the Actor ID)
- [ ] `APIFY_LINKEDIN_ACTOR_ID` remains as a named constant in `apify_client.py` with explanation comment
- [ ] `controller.py` reads cache TTL and timeouts from config
- [ ] Default values match previously hardcoded values exactly
- [ ] Backend boots without errors with default config
- [ ] Run: `grep -rn "api.apify.com" backend/src/ --include="*.py" | grep -v config.py | grep -v __pycache__` — only the Actor ID constant file should reference Apify (via the marketplace link comment)

---

## Notes

- Read the actual files first to capture the EXACT current values. The table above is from the plan.
- The Actor ID decision is explicit — it is NOT configurable. Configurability would be a false promise since changing it breaks response parsing.
- The `ACTOR_SCRAPER_MODE` value — check what it is in the code. If it's a fixed parameter for the Apify actor, it may also be non-configurable (tied to actor behavior).

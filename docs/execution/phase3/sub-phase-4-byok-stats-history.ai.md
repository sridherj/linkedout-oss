# Sub-Phase 4: BYOK Key Management + Stats + Import History

**Goal:** linkedin-ai-production
**Phase:** 3 — Import Pipeline + User-Triggered Enrichment
**Depends on:** SP-3 (Enrichment Pipeline — enrichment_events must exist for stats)
**Estimated effort:** 2-3h
**Source plan sections:** 3.4.1, 3.5.1, 3.5.2

---

## Objective

Add BYOK (Bring Your Own Key) Apify key management, enrichment stats aggregation, and import job history endpoints. This completes the Phase 3 feature set.

## Context

- `EnrichmentConfigEntity` already exists with `apify_key_encrypted` and `apify_key_hint` columns
- `ImportJobEntity` already exists with full counters
- `EnrichmentEventEntity` already exists with `event_type`, `cost_estimate_usd` columns
- Fernet encryption key: `TENANT_SECRET_ENCRYPTION_KEY` env var
- No enrichment cost estimate endpoint needed on backend (reconciliation C4 — computed client-side)

## Pre-Flight Checks

```bash
# Verify enrichment_config entity exists
python -c "from src.linkedout.enrichment_config.entities.enrichment_config_entity import EnrichmentConfigEntity; print('OK')"

# Verify import_job entity exists
python -c "from src.linkedout.import_job.entities.import_job_entity import ImportJobEntity; print('OK')"

# Verify enrichment_event entity
python -c "from src.linkedout.enrichment_event.entities.enrichment_event_entity import EnrichmentEventEntity; print('OK')"
```

## New Dependencies

Add to `pyproject.toml` (if not already present):
```toml
cryptography = ">=42.0"   # Fernet for BYOK key encryption
```

---

## Step 1: BYOK Key Endpoints (3.4.1)

### File

Extend existing enrichment_config controller OR add `src/linkedout/enrichment_pipeline/key_management.py` for encryption logic.

### Endpoints

**`PUT /tenants/{tenant_id}/bus/{bu_id}/enrichment-config/apify-key`**

Request:
```json
{"api_key": "apify_api_xxx..."}
```

Flow:
1. **Validate key:** `GET https://api.apify.com/v2/users/me?token=<key>` → assert 200
2. **Encrypt:** `Fernet(TENANT_SECRET_ENCRYPTION_KEY).encrypt(key.encode())`
3. **Store:** encrypted key + hint (last 4 chars) on enrichment_config
4. **Return:** `{"status": "validated", "key_hint": "...xxx"}`

**`DELETE /tenants/{tenant_id}/bus/{bu_id}/enrichment-config/apify-key`**
- Clear encrypted key + hint

**`GET /tenants/{tenant_id}/bus/{bu_id}/enrichment-config`**
- Return enrichment_mode + key_hint (NEVER the actual key)

### Environment Variable

`TENANT_SECRET_ENCRYPTION_KEY` — Fernet key. Must be in `.env.local` and `.env.test`.

Generate if needed:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

---

## Step 2: Enrichment Stats Endpoint (3.5.1)

### Endpoint

`GET /tenants/{tenant_id}/bus/{bu_id}/enrichment/stats`

### Response

```json
{
  "total_enrichments": 150,
  "cache_hits": 45,
  "cache_hit_rate": 0.30,
  "total_cost_usd": 0.42,
  "saved_via_cache_usd": 0.18,
  "profiles_enriched": 105,
  "profiles_pending": 12,
  "profiles_failed": 3,
  "period": "last_30_days"
}
```

### Implementation

Aggregate query over `enrichment_event` table for the given app_user. Direct query — no materialized view needed at this scale.

---

## Step 3: Import History Endpoints (3.5.2)

### Endpoints

**`GET /tenants/{tenant_id}/bus/{bu_id}/import-jobs`**
- Paginated list of ImportJobEntity for the app_user
- Default sort: `created_at DESC`

**`GET /tenants/{tenant_id}/bus/{bu_id}/import-jobs/{job_id}`**
- Single ImportJob with full counters

---

## Integration Tests

| Test | What's Validated |
|------|-----------------|
| `test_byok_key_lifecycle` | Store key → validate → encrypt → hint visible → delete |
| `test_byok_invalid_key` | Invalid key (mock Apify 401) → rejected |
| `test_enrichment_stats` | After enrichment events exist → stats aggregate correctly |
| `test_import_history` | Create 3 import jobs → list returns 3 in descending order |

---

## Completion Criteria

- [ ] BYOK key validation (live Apify call to verify key)
- [ ] Fernet encryption/decryption of BYOK key working
- [ ] Key hint (last 4 chars) stored and visible, full key never returned
- [ ] DELETE clears key and hint
- [ ] `TENANT_SECRET_ENCRYPTION_KEY` added to `.env.local` and `.env.test`
- [ ] Enrichment stats endpoint returns correct aggregates
- [ ] Import history list endpoint with pagination and descending sort
- [ ] Import history detail endpoint
- [ ] `cryptography` dependency added to pyproject.toml
- [ ] All integration tests pass
- [ ] `precommit-tests` all green — **FULL Phase 3 verification gate**

## Verification

```bash
# Run integration tests for this sub-phase
pytest tests/integration/test_byok_key_management.py tests/integration/test_enrichment_stats.py tests/integration/test_import_history.py -v

# FULL Phase 3 verification — all tests must pass
precommit-tests
```

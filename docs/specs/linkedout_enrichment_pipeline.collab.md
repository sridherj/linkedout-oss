---
feature: linkedout-enrichment-pipeline
module: backend/src/linkedout/enrichment_pipeline
linked_files:
  - backend/src/linkedout/enrichment_pipeline/controller.py
  - backend/src/linkedout/enrichment_pipeline/apify_client.py
  - backend/src/linkedout/enrichment_pipeline/post_enrichment.py
  - backend/src/linkedout/enrichment_pipeline/schemas.py
  - backend/src/linkedout/crawled_profile/services/profile_enrichment_service.py
  - backend/src/organization/enrichment_config/
  - backend/src/utilities/llm_manager/embedding_factory.py
  - backend/src/shared/config/settings.py
version: 1
last_verified: "2026-04-09"
---

# LinkedOut Enrichment Pipeline

**Created:** 2026-04-09 — Adapted from internal spec to OSS implementation

## Intent

Enrich LinkedIn connection profiles by crawling full profile data via Apify, then extracting experiences, education, skills, and companies into relational tables. Supports two modes: platform-managed API keys (round-robin across multiple keys) and BYOK (bring your own key) where the user provides their own Apify key. Includes a 90-day cache to avoid redundant crawls, cost tracking via enrichment events, and post-enrichment processing (embedding generation, search vector population, seniority/function area resolution).

## Behaviors

### Enrichment Trigger

- **Three target resolution methods**: Enrichment can be triggered by profile IDs, connection IDs (resolved to their linked profiles), or all_unenriched flag (selects all profiles with has_enriched_data=False and non-null linkedin_url). Targets are unioned and capped at max_count (default 100, max 1000). Verify all three methods resolve to CrawledProfile entities.

- **90-day cache check**: Profiles with has_enriched_data=True and last_crawled_at within cache_ttl_days (default 90, configurable in settings.py) are skipped with a cache_hit enrichment event. Verify cached profiles are not re-crawled.

- **Cost estimation in trigger response**: The trigger response includes queued count, cached count, skipped_no_url count, and estimated cost in USD (queued x cost_per_profile_usd, default $0.004/profile). Verify cost estimation is accurate.

- **Synchronous enrichment with retry**: Each non-cached profile is enriched synchronously (not via task queue) with 3 retry attempts and exponential backoff (1s, 2s, 4s). On final failure, the enrichment event is marked as 'failed'. Verify retry behavior and failure marking.

> Edge: Profiles without a linkedin_url are skipped entirely (skipped_no_url counter). They cannot be enriched via Apify.

### Apify Client

- **Platform key round-robin**: Platform mode resolves keys from APIFY_API_KEYS (comma-separated) or falls back to single APIFY_API_KEY. Multiple keys are rotated via itertools.cycle at module level for true round-robin across calls. Verify all configured keys are used in rotation.

- **Synchronous single-profile enrichment**: The primary enrichment path calls run-sync-get-dataset-items with a configurable timeout (sync_timeout_seconds, default 60s). Returns the first item from the response or None on failure. Success is checked via resp.ok (accepts any 2xx status, since Apify returns HTTP 201 on successful run creation). Verify timeout is enforced and non-2xx responses are treated as failures.

- **Apify actor input format**: The actor (LpVuK3Zozwuipa5bp) requires profileScraperMode and queries fields. The queries field is a list of LinkedIn profile URLs. The scraper mode is hardcoded to "Profile details no email ($4 per 1k)". Verify the input payload uses queries, not startUrls.

- **Async multi-profile support**: An alternative path starts an async Apify run for multiple URLs and polls for completion with configurable timeout (run_poll_timeout_seconds default 300s, run_poll_interval_seconds default 5s). Results are fetched from the dataset after completion. Verify polling respects timeout and handles FAILED/ABORTED/TIMED-OUT statuses.

### Post-Enrichment Processing

- **Two-phase processing**: PostEnrichmentService handles Apify response mapping and delegates structured row creation to ProfileEnrichmentService.enrich(). The post-enrichment service maps Apify JSON to CrawledProfile columns, then the enrichment service handles experience/education/skill rows, search_vector, and embedding.

- **Profile field mapping from Apify response**: Maps Apify JSON fields to CrawledProfile columns: full_name (from firstName + lastName), public_identifier, headline, about, location (parsed city/state/country/countryCode from location.parsed), connections_count, follower_count, open_to_work, premium, current_company_name (from currentPosition[0]), current_position (from first experience with end_date "present"), profile_image_url (from profilePicture.url), raw_profile (full JSON). Verify all mapped fields are persisted.

- **Experience extraction with company resolution**: ProfileEnrichmentService deletes existing experiences for the profile (idempotent re-enrichment via delete+insert), then creates ExperienceEntity rows. Company IDs are resolved via CompanyMatcher + resolve_company utility. Supports start/end dates with month name parsing. Each experience also gets role alias lookup for seniority_level and function_area. Verify re-enrichment replaces rather than duplicates experiences.

- **Education extraction**: Deletes existing education rows then creates EducationEntity rows with school name, school LinkedIn URL, degree, field of study, start/end years, and description. Verify re-enrichment is idempotent.

- **Skills extraction from two sources**: Extracts skills from both the "skills" array (dict with .name field) and "topSkills" array (plain strings) in Apify data. Deduplicates by skill name within a profile. Verify no duplicate skills per profile.

- **Company resolution via CompanyMatcher**: Pre-loads all existing companies into an in-memory CompanyMatcher. New companies are created on the fly via resolve_company utility with canonical_name, linkedin_url, and universal_name. Both PostEnrichmentService and ProfileEnrichmentService independently pre-load companies. Verify company dedup works across enrichments.

- **Embedding generation**: Uses the configured EmbeddingProvider (via embedding_factory) to generate a vector embedding from the profile's full_name, headline, about, and experience data (via build_embedding_text). The embedding column is determined dynamically by get_embedding_column_name (e.g., embedding_openai or embedding_nomic). Also sets embedding_model, embedding_dim, and embedding_updated_at. Failed embeddings are logged to data/failed_embeddings.jsonl for later retry. Verify embedding is generated for enriched profiles.

- **Search vector population**: Concatenates full_name + headline + about + experience companies/positions into a text field (search_vector) for full-text search. Verify search_vector is populated on enrichment.

- **Seniority and function area from role alias**: PostEnrichmentService looks up the role_alias table for an exact match on current_position. If found, sets seniority_level and function_area on the crawled_profile. Additionally, ProfileEnrichmentService performs per-experience role alias lookup, setting seniority_level and function_area on each ExperienceEntity. Verify seniority_level is populated when a matching role alias exists.

- **Race condition guard**: PostEnrichmentService re-checks if the profile was already enriched within 90 days before processing (concurrent enrichment may have completed). If so, marks the event as cache_hit and returns. ProfileEnrichmentService uses SELECT ... FOR UPDATE to serialize concurrent enrichments for the same profile. Verify concurrent enrichments do not duplicate work.

- **Stub profile creation**: If no CrawledProfile exists for the linkedin_url being enriched, PostEnrichmentService creates a stub profile with linkedin_url and data_source='apify' before proceeding. Verify stub creation works for profiles not yet in the database.

### BYOK Key Management

- **Key validation against Apify API**: The set-key endpoint (PUT /enrichment/apify-key) validates the key by calling Apify's users/me endpoint with configurable timeout (key_validation_timeout_seconds, default 15s). Non-200 responses return HTTP 400. Verify validation catches bad keys.

- **Key encryption at rest**: Valid keys are encrypted using Fernet with TENANT_SECRET_ENCRYPTION_KEY environment variable and stored on EnrichmentConfig. Only a 4-character hint (last 4 chars) is exposed. Verify raw keys are never stored in the database.

- **Key deletion resets to platform mode**: The delete-key endpoint (DELETE /enrichment/apify-key) clears the encrypted key and hint, resets enrichment_mode to 'platform'. Returns 204 on success, 404 if no config exists. Verify deletion is complete.

- **Config read endpoint**: The get-config endpoint (GET /enrichment/config) returns the current enrichment_mode and key_hint (if BYOK). Platform mode is the default when no config exists. Verify platform mode is the default.

### Enrichment Stats

- **30-day rolling stats endpoint**: The stats endpoint (GET /enrichment/stats) aggregates enrichment events for the last 30 days scoped to tenant+BU. Returns total enrichments, cache hits, cache hit rate, total cost USD, savings from cache, and status breakdowns (profiles_enriched from 'crawled'+'completed' events, profiles_pending from 'queued', profiles_failed from 'failed'). Verify stats are scoped to tenant+BU.

## Decisions

### Platform key round-robin via comma-separated APIFY_API_KEYS — 2026-04-09
**Chose:** Round-robin across comma-separated APIFY_API_KEYS via itertools.cycle, with APIFY_API_KEY single-key fallback
**Over:** Numbered APIFY_API_KEY_1 through _9 env vars (internal version)
**Because:** Comma-separated is simpler to configure and supports arbitrary count. Module-level cycle state persists across requests for even distribution.

### Fernet encryption for BYOK keys — 2026-03-27
**Chose:** Fernet symmetric encryption with TENANT_SECRET_ENCRYPTION_KEY
**Over:** Storing keys in a secrets manager or hashing
**Because:** Keys must be recoverable (used to call Apify). Fernet is simple, auditable, and the encryption key is in env vars.

### Idempotent re-enrichment via delete+insert — 2026-03-27
**Chose:** Delete all existing experiences/education/skills for a profile before inserting new ones
**Over:** Upsert or diff-based merge
**Because:** Apify returns the complete current state. Delete+insert is simpler and guarantees no stale data from prior enrichments.

### Apify input format: queries over startUrls — 2026-03-28
**Chose:** `profileScraperMode` + `queries` input format
**Over:** `startUrls` array-of-objects format
**Because:** The startUrls format was incorrect for actor LpVuK3Zozwuipa5bp and caused silent empty results.

### Synchronous enrichment over task queue — 2026-04-09
**Chose:** Synchronous enrichment with retry in the request handler
**Over:** Procrastinate task queue for async enrichment (internal version)
**Because:** OSS removed the Procrastinate dependency. Synchronous with retry (3 attempts, exponential backoff) is simpler for single-user deployments.

## Not Included

- Procrastinate/task queue for async enrichment (removed in OSS; enrichment runs synchronously)
- Webhook-based enrichment for large batches
- Proactive cache refresh cron
- Materialized view for enrichment stats
- Batch embedding calls
- Enrichment scheduling or priority queue

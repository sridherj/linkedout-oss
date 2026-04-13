---
feature: linkedout-enrichment-pipeline
module: backend/src/linkedout/enrichment_pipeline
linked_files:
  - backend/src/linkedout/enrichment_pipeline/controller.py
  - backend/src/linkedout/enrichment_pipeline/apify_client.py
  - backend/src/linkedout/enrichment_pipeline/bulk_enrichment.py
  - backend/src/linkedout/enrichment_pipeline/post_enrichment.py
  - backend/src/linkedout/enrichment_pipeline/schemas.py
  - backend/src/linkedout/crawled_profile/services/profile_enrichment_service.py
  - backend/src/organization/enrichment_config/
  - backend/src/utilities/llm_manager/embedding_factory.py
  - backend/src/shared/config/settings.py
  - backend/src/shared/utils/apify_archive.py
version: 7
last_verified: "2026-04-13"
---

# LinkedOut Enrichment Pipeline

**Created:** 2026-04-09 — Adapted from internal spec to OSS implementation
**Updated:** 2026-04-13 — Added pre-run recovery sweep, state rotation, dry-run recovery awareness

## Intent

Enrich LinkedIn connection profiles by crawling full profile data via Apify, then extracting experiences, education, skills, and companies into relational tables. Supports two modes: platform-managed API keys (round-robin across multiple keys) and BYOK (bring your own key) where the user provides their own Apify key. Includes a 90-day cache to avoid redundant crawls, cost tracking via enrichment events, and post-enrichment processing (embedding generation, search vector population, seniority/function area resolution). Bulk enrichment dispatches up to N batches concurrently to Apify, polling all in a single loop, with crash-safe resume from an append-only state file.

## Behaviors

### Enrichment Trigger

- **Three target resolution methods**: Enrichment can be triggered by profile IDs, connection IDs (resolved to their linked profiles), or all_unenriched flag (selects all profiles with has_enriched_data=False and linkedin_url containing "linkedin.com/"). Stub URLs (e.g. `stub://gmail-...` from non-LinkedIn contact imports) are excluded. Targets are unioned and capped at max_count (default 100, max 1000). Verify all three methods resolve to CrawledProfile entities.

- **90-day cache check**: Profiles with has_enriched_data=True and last_crawled_at within cache_ttl_days (default 90, configurable in settings.py) are skipped with a cache_hit enrichment event. Verify cached profiles are not re-crawled.

- **Cost estimation in trigger response**: The trigger response includes queued count, cached count, skipped_no_url count, and estimated cost in USD (queued x cost_per_profile_usd, default $0.004/profile). Verify cost estimation is accurate.

- **Synchronous enrichment with retry**: Each non-cached profile is enriched synchronously (not via task queue) with 3 retry attempts and exponential backoff (1s, 2s, 4s). On final failure, the enrichment event is marked as 'failed'. Verify retry behavior and failure marking.

> Edge: Profiles without a linkedin_url, or with non-LinkedIn URLs (e.g. `stub://` placeholders from contact imports), are skipped entirely (skipped_no_url counter). Only URLs containing "linkedin.com/" are sent to Apify.

### Apify Client

- **Platform key round-robin**: Platform mode resolves keys from APIFY_API_KEYS (comma-separated) or falls back to single APIFY_API_KEY. Multiple keys are rotated via itertools.cycle at module level for true round-robin across calls. Verify all configured keys are used in rotation.

- **Synchronous single-profile enrichment**: The primary enrichment path calls run-sync-get-dataset-items with a configurable timeout (sync_timeout_seconds, default 60s). Returns the first item from the response or None on failure. Success is checked via resp.ok (accepts any 2xx status, since Apify returns HTTP 201 on successful run creation). Verify timeout is enforced and non-2xx responses are treated as failures.

- **Apify actor input format**: The actor (LpVuK3Zozwuipa5bp) requires profileScraperMode and queries fields. The queries field is a list of LinkedIn profile URLs. The scraper mode is hardcoded to "Profile details no email ($4 per 1k)". Verify the input payload uses queries, not startUrls.

- **Async multi-profile support**: An alternative path starts an async Apify run for multiple URLs and polls for completion with configurable timeout (run_poll_timeout_seconds default 900s, run_poll_interval_seconds default 5s). Results are fetched from the dataset after completion. Verify polling respects timeout and handles FAILED/ABORTED/TIMED-OUT statuses.

- **Non-blocking status check**: `check_run_status()` performs a single non-blocking GET to the Apify actor-runs endpoint. Returns `(status, dataset_id)` for terminal states (SUCCEEDED, FAILED, ABORTED, TIMED-OUT) or `None` if still running. This is the primitive used by the concurrent dispatch-pool — the caller controls polling cadence. Verify it does not sleep or loop.

### Bulk Batch Enrichment

- **Dispatch-pool pattern**: `enrich_profiles()` maintains a pool of up to `max_parallel_batches` (default 5, configurable in `EnrichmentConfig`) concurrent Apify runs. A `pending` deque holds undispatched batches; an `inflight` dict tracks dispatched runs by batch index. The loop fills empty slots from pending, polls all inflight batches via `check_run_status()`, processes completed batches immediately (serialized in the main thread), and sleeps `run_poll_interval_seconds` between poll cycles. Post-processing (DB writes, embeddings) stays serialized — concurrency is only in the Apify wait time. Verify that with `max_parallel_batches=1`, behavior is identical to sequential execution.

- **Crash-safe resume via append-only JSONL state file**: Each batch progresses through `batch_started` → `batch_fetched` → `profile_processed` (per profile) → `batch_completed` events, written to `{data_dir}/enrichment/enrich-state.jsonl`. On resume, `_load_state()` reconstructs per-batch state indexed by `batch_idx`. Events from concurrent batches may interleave — this is safe because the index is per-batch. Verify that a crash at any point (mid-dispatch, mid-poll, mid-processing) resumes correctly without re-dispatching existing Apify runs.

- **Resume classification via `_check_batch_resume()`**: A pure function that classifies each batch into one of four actions based on state file history: `skip` (already completed), `process` (results on disk, not all profiles processed), `poll` (dispatched but not fetched — add to inflight, NO re-dispatch), `dispatch` (not started). Returns a `BatchResumeResult` dataclass with action, run_id, cached results, and already-processed URL set. Verify each resume action independently.

- **Disk cache before fetch**: Before calling `fetch_results()` on a completed run, the loop checks `_load_results()` for previously-saved results on disk. If results exist (from a prior session that fetched but crashed before writing `batch_fetched`), the Apify API call is skipped. Verify that resume with results on disk does not call `fetch_results()`.

- **Decoupled poll key**: Each poll cycle calls `_get_key()` for any healthy key — the poll key is not tied to the dispatch key. Any Apify key can poll any run (polling is a GET, not billable). If a key is revoked after dispatch, polling continues with other healthy keys. Verify that key revocation mid-flight does not block polling of in-flight batches.

- **Per-batch error isolation**: Each `check_run_status()` and `fetch_results()` call is wrapped in try/except. One batch's HTTP error does not affect other batches in the same poll cycle — the errored batch is retried next cycle. Verify that a poll error for one batch does not block processing of another batch that completed in the same cycle.

- **Timeout per batch**: Each inflight batch tracks its dispatch time. If `time.time() - dispatch_time > run_poll_timeout_seconds`, the batch is removed from inflight (not re-dispatched) and logged as a warning (not an error) with a note that recovery will be attempted on next run. It remains in state as `batch_started` and can be resumed in a future run. Verify that timed-out batches do not block other inflight batches.

- **Key exhaustion handling**: If all keys become exhausted or invalid during the fill phase, dispatch stops (`stopped_reason = 'all_keys_exhausted'`). If all keys die during the poll phase, the loop breaks — inflight batches are tracked in state for future resume. Verify that key exhaustion stops new dispatches but does not lose track of inflight batches.

- **Pre-run recovery sweep**: Before querying for unenriched profiles, `recover_incomplete_batches()` scans the state file for batches with `batch_started` but no `batch_completed`. For each incomplete batch, it checks Apify run status: SUCCEEDED runs have their results fetched and processed, FAILED/ABORTED/TIMED-OUT runs are marked failed, and still-running batches are skipped. Uses URLs from the state file (not a fresh DB query) to avoid index collisions. Returns a `RecoverySummary` with recovered, failed, still_running, and batches_recovered counts. After recovery, the DB is re-queried to exclude profiles that were just recovered. Verify that a crash mid-batch followed by re-run completes the batch without re-dispatching to Apify.

- **State file rotation after recovery**: When `recover_incomplete_batches()` resolves all prior batches (none still running), it renames the state file from `.jsonl` to `.jsonl.prev` via `_rotate_state()`. This prevents batch index collisions between the old run's indices and the new run's indices. If any batches are still running, rotation is deferred to the next invocation. Verify that rotation only occurs when no batches remain in-flight.

- **Dry-run awareness of recoverable batches**: In dry-run mode, `check_recoverable_batches()` performs a read-only scan of the state file and checks Apify run statuses without fetching results or writing state. The dry-run output reports recoverable and still-running counts separately from truly unenriched profiles. Verify that dry-run does not modify the state file or fetch Apify dataset results.

- **RecoverySummary dataclass**: Recovery functions return a `RecoverySummary(recovered, failed, still_running, batches_recovered)` dataclass summarizing the outcome. This is used by both the full run (to log results) and the dry run (to report counts). Verify all four fields are populated accurately.

### Post-Enrichment Processing

- **JSONL archive of raw Apify responses**: Before any database writes, PostEnrichmentService appends the raw Apify response to `{data_dir}/crawled/apify-responses.jsonl` as a single JSON line with metadata envelope (`archived_at`, `linkedin_url`, `source`, `data`). Archive writes are fire-and-forget — failures are logged but do not block enrichment. This ensures crawled data survives database loss. Verify archive file is appended on each enrichment.

- **Two-phase processing**: PostEnrichmentService handles Apify response mapping and delegates structured row creation to ProfileEnrichmentService.enrich(). The post-enrichment service maps Apify JSON to CrawledProfile columns, then the enrichment service handles experience/education/skill rows, search_vector, and embedding. In batch mode (`process_batch`), a single ProfileEnrichmentService is hoisted before the loop and shared across all profiles to avoid redundant company preloading. In single-profile mode (`process_enrichment_result` without `enrichment_service`), a new service is created per call.

- **Profile field mapping from Apify response**: Maps Apify JSON fields to CrawledProfile columns: full_name (from firstName + lastName), public_identifier, headline, about, location (parsed city/state/country/countryCode from location.parsed), connections_count, follower_count, open_to_work, premium, current_company_name (from currentPosition[0]), current_position (from first experience with end_date "present"), profile_image_url (from profilePicture.url), raw_profile (full JSON). Verify all mapped fields are persisted.

- **Experience extraction with company resolution**: ProfileEnrichmentService deletes existing experiences for the profile (idempotent re-enrichment via delete+insert), then creates ExperienceEntity rows. Company IDs are resolved via CompanyMatcher + resolve_company utility. Supports start/end dates with month name parsing. Each experience also gets role alias lookup for seniority_level and function_area. Verify re-enrichment replaces rather than duplicates experiences.

- **Education extraction**: Deletes existing education rows then creates EducationEntity rows with school name, school LinkedIn URL, degree, field of study, start/end years, and description. Verify re-enrichment is idempotent.

- **Skills extraction from two sources**: Extracts skills from both the "skills" array (dict with .name field) and "topSkills" array (plain strings) in Apify data. Deduplicates by skill name within a profile. Verify no duplicate skills per profile.

- **Company resolution via CompanyMatcher**: Pre-loads all existing companies into an in-memory CompanyMatcher. New companies are created on the fly via resolve_company utility with canonical_name, linkedin_url, and universal_name. ProfileEnrichmentService accepts an optional `company_matcher` + `company_by_canonical` in its constructor — when provided (e.g. from PostEnrichmentService during batch processing), it skips its own preload and shares the caller's matcher. When omitted (single-profile API path), it preloads independently. Verify company dedup works across enrichments.

- **Embedding generation**: Uses the configured EmbeddingProvider (via embedding_factory) to generate a vector embedding from the profile's full_name, headline, about, and experience data (via build_embedding_text). The embedding column is determined dynamically by get_embedding_column_name (e.g., embedding_openai or embedding_nomic). Also sets embedding_model, embedding_dim, and embedding_updated_at. Failed embeddings are logged to data/failed_embeddings.jsonl for later retry. Verify embedding is generated for enriched profiles.

- **Search vector population**: Concatenates full_name + headline + about + experience companies/positions into a text field (search_vector) for full-text search. Verify search_vector is populated on enrichment.

- **Seniority and function area from role alias**: PostEnrichmentService looks up the role_alias table for an exact match on current_position. If found, sets seniority_level and function_area on the crawled_profile. Additionally, ProfileEnrichmentService performs per-experience role alias lookup, setting seniority_level and function_area on each ExperienceEntity. Verify seniority_level is populated when a matching role alias exists.

- **Race condition guard**: PostEnrichmentService re-checks if the profile was already enriched within 90 days before processing (concurrent enrichment may have completed). If so, marks the event as cache_hit and returns. ProfileEnrichmentService uses SELECT ... FOR UPDATE to serialize concurrent enrichments for the same profile. Verify concurrent enrichments do not duplicate work.

- **Stub profile creation**: If no CrawledProfile exists for the linkedin_url being enriched, PostEnrichmentService creates a stub profile with linkedin_url and data_source='apify' before proceeding. Verify stub creation works for profiles not yet in the database.

- **LinkedIn slug redirect handling**: LinkedIn may resolve profile slugs to a different canonical form (e.g. stripping display name suffixes, removing emoji, normalizing hyphens). When Apify returns a `linkedinUrl` that differs from the input URL (after normalization), the system: (a) matches the result to the input via rapidfuzz greedy slug matching, (b) updates `linkedin_url` to the Apify canonical URL, and (c) stores the original URL in `previous_linkedin_url` for import dedup safety. The import pipeline checks both `linkedin_url` and `previous_linkedin_url` when deduplicating re-imports.

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

### Concurrent dispatch-pool over sequential batch loop — 2026-04-13
**Chose:** Synchronous dispatch-pool with `time.sleep()` polling in a single thread
**Over:** asyncio event loop with async HTTP client and async DB sessions
**Because:** The bottleneck is Apify processing time (5-13 min per batch), not our poll overhead (~250ms for 5 batches). asyncio would require async DB sessions and HTTP client for ~250ms savings per 5s cycle — not worth the complexity. The dispatch-pool overlaps Apify wait time across N batches, reducing wall-clock from ~5h to ~1-1.5h for 1,759 profiles.

### `_check_batch_resume()` pure function for resume classification — 2026-04-13
**Chose:** Extract resume logic into a pure function returning a `BatchResumeResult` dataclass
**Over:** Inline 4-way branching in the main loop (~130 lines)
**Because:** The main dispatch-pool loop is already complex. A pure function with 4 clear return values is independently testable (5 unit tests) and keeps the loop body focused on dispatch/poll/process.

### `previous_linkedin_url` for redirect tracking — 2026-04-13
**Chose:** Single `previous_linkedin_url` column on CrawledProfile
**Over:** JSONB array of aliases or separate alias table
**Because:** LinkedIn redirects are rare (~2-5%) and typically happen once. A single column handles the common case without schema complexity. If a profile redirects multiple times (extremely rare), only the most recent previous URL is preserved.

## Known Limitations

- **Similar-slug collision in fuzzy matching**: If two profiles with similar slugs (e.g. `abhishek-mishra-developer` and `abhishek-mishra1-engineer`) both redirect in the same batch, the rapidfuzz greedy matcher could cross-pair them. This requires: similar slugs + same batch + both redirect — extremely rare in practice since LinkedIn CSV is date-sorted (not alphabetical) so similar names are naturally spread across batches. Accepted risk; revisit if observed in production.

- **Dispatch-state-write gap (~10ms)**: If the process dies after Apify accepts a run but before `batch_started` is written to the state file, the run is orphaned. On resume, the same URLs would be re-dispatched (~$0.40 worst case per batch of 100). The window is ~10ms between HTTP response and local file write. Pre-existing in the sequential code; not worsened by concurrent batches. Documented for future hardening (e.g. pre-dispatch events or Apify run list queries on resume).

## Not Included

- Procrastinate/task queue for async enrichment (removed in OSS; enrichment runs synchronously)
- Proactive cache refresh cron
- Materialized view for enrichment stats
- Enrichment scheduling or priority queue
- Dispatch-state-write gap hardening (pre-dispatch events, Apify run list queries on resume)

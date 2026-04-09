---
feature: linkedout-affinity-scoring
module: backend/src/linkedout/intelligence/scoring
linked_files:
  - backend/src/linkedout/intelligence/scoring/affinity_scorer.py
  - backend/src/linkedout/commands/compute_affinity.py
  - backend/src/shared/config/settings.py
  - backend/tests/integration/linkedout/import_pipeline/test_import_pipeline.py
version: 1
last_verified: "2026-04-09"
---

# LinkedOut Affinity Scoring

**Created:** 2026-04-09 -- Adapted from internal spec for LinkedOut OSS

## Intent

Compute a relationship-strength score (0-100) for each connection in a user's network, then assign Dunbar-layer tiers by rank. The score synthesizes five signals (career overlap, external contacts, embedding similarity, source count, recency) into a single comparable number. Affinity scores power warm-intro ranking, search result ordering, and network health dashboards.

## Behaviors

### Scoring Formula (V3 - Current)

- **Five-signal weighted score**: Affinity score is computed from career_overlap (weight 0.40), external_contact (weight 0.25), embedding_similarity (weight 0.15), source_count (weight 0.10), and recency (weight 0.10). The raw weighted sum is scaled to 0-100 via `round(raw * 100, 1)`. All weights are configurable via `ScoringConfig` in `settings.py`. Verify weights sum to 1.0 and score range is 0-100.

- **Source count normalization**: The number of distinct import sources for a connection is normalized to a 0-1 signal via `SOURCE_COUNT_MAP`: 1 source=0.2, 2=0.5, 3=0.8, 4+=1.0 (map uses `.get(count, 1.0)` for 4+). Zero or negative source counts return 0.0. Source count is derived from `len(connection.sources)` where `sources` is a PostgreSQL ARRAY column. Verify normalization follows the defined map.

- **Recency decay**: Connection age is bucketed into decay tiers via configurable `recency_thresholds` in `ScoringConfig`: less than 12 months=1.0, 12-36 months=0.7, 36-60 months=0.4, 60+ months=0.2 (fallback). Null `connected_at` returns 0.0. Months are calculated as `(ref - connected_at).days * 12 / 365.25`. Verify decay tiers are correctly applied.

- **Company-size normalized career overlap**: Career overlap is weighted by company size using `1.0 / log2(employee_count + 2)` dampening -- sharing a 10-person startup scores much higher than both working at a 50K-person company. A seniority boost multiplier is applied per shared-company pair based on `max(user_seniority, connection_seniority)`: founder=3.0, c_suite=2.5, vp=2.0, director=1.8, manager=1.5, lead=1.3, senior=1.1, mid=1.0 (baseline), junior=0.9, intern=0.7. NULL seniority defaults to mid (1.0). Temporal overlap (months of concurrent employment) is factored in: `overlap_months * size_factor * seniority_boost`, normalized by `min(total / 36.0, 1.0)`. Employee count defaults to 500 when unknown (`employee_count or 500`). Returns 0.0 if either side has no experiences or `own_crawled_profile_id` is NULL. All seniority boosts and the normalization denominator (36 months) are configurable via `ScoringConfig`. Verify small-company overlap scores higher than large-company overlap. Verify founder-level overlap scores higher than mid-level at same company. Verify 0.0 when user has no linked profile.

- **External contact signal**: Connections confirmed through external contact sources receive a warmth bonus. Scoring is cap-at-highest-tier per connection: phone in any source = 1.0, email-only = 0.7 (configurable via `ScoringConfig.external_contact_scores`). Multiple sources do NOT stack -- having email in both Google Contacts and Gmail still scores 0.7. Contact data comes from the `contact_source` table filtered to `dedup_status = 'matched'` and source types in `EXTERNAL_SOURCE_TYPES = {google_contacts_job, gmail_email_only, contacts_phone}`. Verify bonus applies only when contact_source rows exist for the connection. Verify phone beats email regardless of source count.

- **Embedding similarity signal**: Cosine similarity between the user's own profile embedding and each connection's profile embedding. The active embedding column is dynamically selected based on the configured embedding provider via `get_embedding_column_name()` -- either `embedding_openai` (for OpenAI models) or `embedding_nomic` (for local nomic models). Computed DB-side via pgvector's `<=>` (cosine distance) operator: `similarity = 1 - distance`. Clamped to `max(0.0, ...)`. Returns 0.0 when either embedding is missing. Batch-fetched for all connections in `compute_for_user`. Verify signal is 0.0 when either embedding is missing.

### Dunbar Tier Assignment

- **Rank-based tier assignment**: After scoring all connections for a user, connections are sorted by score descending (tiebreak: connection ID ascending for determinism). Tiers are assigned by rank position: top 15 = inner_circle, 16-50 = active, 51-150 = familiar, 151+ = acquaintance. All cutoffs are configurable via `ScoringConfig` (`dunbar_inner_circle=15`, `dunbar_active=50`, `dunbar_familiar=150`). Verify tiers are assigned by rank, not by absolute score.

### Batch Computation

- **Full user recomputation**: `compute_for_user()` processes all connections for a given `app_user_id` in a single pass. Career data is batch-fetched: user experiences in one query, all connection experiences in one JOIN query (Connection -> CrawledProfile -> Experience), company sizes in one query, external contacts in one query, embedding similarities in one raw SQL query. Scores are written via bulk `UPDATE` using SQLAlchemy's `update()` with a list of parameter dicts. Dunbar tiers are assigned after scoring. The operation is atomic within the session. Verify batch update count matches connection count.

- **Single connection recomputation**: `compute_for_connection()` updates one connection's score and signal breakdowns but does NOT reassign Dunbar tiers (that requires full user recomputation to re-rank). Verify single-connection update does not change other connections' tiers.

- **CLI compute-affinity command**: The `linkedout compute-affinity` command runs batch recomputation for all active users. Iterates each user in a separate DB session (one session per user for RLS scoping). Accepts `--dry-run` to report user count without computing. Accepts `--force` to recompute all (vs. only unscored, though current implementation always recomputes all). Verify dry-run writes no changes.

### Signal Breakdowns

- **Per-connection signal storage**: Each connection stores the individual signal values alongside the composite score: `affinity_source_count`, `affinity_recency`, `affinity_career_overlap`, `affinity_mutual_connections` (placeholder at 0.0), `affinity_external_contact`, `affinity_embedding_similarity`. Also stores `affinity_computed_at` timestamp and `affinity_version` (currently 3). Verify all breakdown fields are populated after scoring.

### Configuration

- **All weights and thresholds in ScoringConfig**: The `ScoringConfig` Pydantic model in `settings.py` centralizes all scoring parameters: 5 signal weights, 3 Dunbar tier cutoffs, 10 seniority boost values, 2 external contact scores, career normalization months, and recency thresholds. All have sensible defaults and can be overridden via config.

### Edge Cases

> Edge: Career overlap returns 0.0 if the user's `own_crawled_profile_id` is NULL. Until the user links their own profile, all career overlap scores are 0.

> Edge: Source count is derived from `connection.sources` array length. A connection with NULL sources returns 0.0 for source_count signal (`len(conn.sources) if conn.sources else 0`).

> Edge: contact_source table may have 0 rows. External contact signal produces 0.0 for all connections until contact import is run.

> Edge: Embedding similarity uses the active embedding provider's column (`embedding_openai` or `embedding_nomic`). Connections without embeddings for the active provider produce 0.0 for this signal, even if they have embeddings for the other provider.

> Edge: Missing seniority_level on an experience defaults to mid (boost=1.0), preserving existing behavior for experiences without seniority data.

> Edge: V3 degradation -- with no contact_source rows and no embeddings, scoring degrades to `source_count * 0.10 + recency * 0.10 = max 20 points`. This is intentional -- the formula rewards richer data.

## Decisions

### Rank-based Dunbar tiers over absolute score thresholds -- 2026-03-28
**Chose:** Assign tiers by rank position after sorting
**Over:** Fixed score thresholds (e.g., >70 = inner_circle)
**Because:** Score distributions vary by user. A user with 50 connections should still have an inner_circle. Rank-based ensures every user has a meaningful tier distribution regardless of absolute scores.

### Career overlap: size-normalized temporal overlap -- 2026-03-28
**Chose:** `overlap_months * (1/log2(employee_count+2)) * seniority_boost`, normalized by `min(total/36.0, 1.0)`
**Over:** Jaccard overlap with max(5, union) floor
**Because:** Working at the same 10-person startup indicates a much stronger relationship than both having worked at Google (50K+ employees). Temporal overlap captures actual concurrent employment rather than just shared employer names.

### Weight rebalancing -- 2026-03-28
**Chose:** career_overlap 0.40, external_contact 0.25, embedding_similarity 0.15, source_count 0.10, recency 0.10
**Over:** Equal-weight source_count + recency
**Because:** Career overlap and external contacts are higher-fidelity indicators of real-world relationship strength than source count (which just reflects data availability) or recency (which penalizes long-term relationships).

### External contact cap-at-highest-tier over stacking -- 2026-03-28
**Chose:** phone=1.0, email-only=0.7, no stacking across sources
**Over:** Additive stacking or source-weighted scoring
**Because:** The signal answers "do I know this person outside LinkedIn?" -- that's binary with a quality gradient. Having someone's email in both Google and iCloud doesn't make the relationship warmer.

### Seniority boost multiplier over effective-size approach -- 2026-04-04
**Chose:** Multiplicative seniority boost on career_overlap per shared-company pair
**Over:** Reducing effective company size based on seniority
**Because:** Simpler to reason about, degrades gracefully (missing seniority = 1.0 = no change), and boost values are independently tunable per seniority level without affecting the base size_factor curve.

### Configurable scoring via ScoringConfig -- 2026-04-09
**Chose:** All weights, thresholds, and boosts in a Pydantic `ScoringConfig` model
**Over:** Hardcoded constants in the scorer module
**Because:** OSS users may want to tune scoring for their own network characteristics without modifying scorer code. Defaults match the eyeball-tuned values from the internal version.

### Dual embedding provider support -- 2026-04-09
**Chose:** Dynamic embedding column selection via `get_embedding_column_name()`
**Over:** Hardcoded `embedding` column for text-embedding-3-small
**Because:** OSS supports both OpenAI (`embedding_openai`) and local nomic (`embedding_nomic`) embedding providers. The scorer uses whichever column the active provider maps to.

## Not Included

- Mutual connections signal (placeholder at 0.0 on connection entity -- requires crawling mutual connection data)
- Automated recomputation triggers (currently manual via CLI; no event-driven recompute on import/enrichment)
- Interaction-based signals (message frequency, meeting history) -- out of scope for network-data-only scoring
- Score explanation / justification generation
- Per-user weight tuning (all users share the same ScoringConfig weights)

## Cross-References

- [LinkedOut Import Pipeline](linkedout_import_pipeline.collab.md) -- Contact imports populate the `contact_source` table that drives the external contact signal
- [LinkedOut Data Model](linkedout_data_model.collab.md) -- Connection entity columns (affinity_*, dunbar_tier), AppUser.own_crawled_profile_id, contact_source table, dual embedding columns on crawled_profile

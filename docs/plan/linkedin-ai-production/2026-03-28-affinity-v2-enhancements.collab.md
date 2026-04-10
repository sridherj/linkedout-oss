# Affinity V2: External Contact Signal, Company-Size Normalization, and Embedding Similarity

## Overview

Enhance the `AffinityScorer` from its V1 three-signal formula (source_count, recency, career_overlap) to V2 with five signals: company-size normalized career overlap, external contact warmth, embedding similarity, plus reduced-weight source_count and recency. The implementation ports proven logic from two old second-brain scripts (`compute_affinity.py` for company-size normalization, `enrich_affinity_gmail.py` for external contact matching) while adding a new embedding similarity signal that leverages existing 1536-dim vectors on `crawled_profile`. The affinity scoring spec (`linkedout_affinity_scoring.collab.md`) documents the V2 planned behaviors -- this plan implements them.

## Operating Mode

**HOLD SCOPE** -- The high-level plan scopes Phase 3 to three specific enhancements (external contact signal, company-size normalization, embedding similarity) plus V2 weight revision. No signals for expansion or reduction. Rigorous adherence to the spec'd V2 behaviors.

## Sub-phase 1: Schema Migration -- New Signal Columns on Connection Entity

**Outcome:** The `connection` table has two new float columns (`affinity_external_contact`, `affinity_embedding_similarity`) with defaults of 0.0. The `contact_source` table gains a `source_label` VARCHAR(50) column to distinguish import origins (e.g., `google_personal`, `google_work`, `icloud`, `office365`). The `ConnectionEntity` and `ContactSourceEntity` have corresponding mapped columns. Existing V1 scores are untouched. Migration is reversible.

**Dependencies:** None

**Estimated effort:** 0.5 session (~1 hour)

**Verification:**
- `alembic upgrade head` runs without error
- `psql $DATABASE_URL -c "\d connection"` shows both new columns with default 0.0
- `pytest tests/linkedout/connection/repositories/test_connection_repository.py -v` passes (entity still wires correctly)
- Existing affinity_score values are unchanged after migration

Key activities:

- Add two new columns to `ConnectionEntity` in `src/linkedout/connection/entities/connection_entity.py`:
  ```python
  affinity_external_contact: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='External contact warmth signal')
  affinity_embedding_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Embedding similarity signal')
  ```
  Place them after `affinity_mutual_connections` to keep signal columns grouped.

- Add `source_label` column to `ContactSourceEntity` (if entity exists) or to the `contact_source` table directly:
  ```python
  source_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Import origin: google_personal, google_work, icloud, office365')
  ```
  Known values: `google_personal`, `google_work`, `icloud`, `office365`. Nullable for backward compat with any future bulk imports that don't specify origin.

- Generate Alembic migration: `alembic revision --autogenerate -m "add_affinity_v2_signal_columns_and_contact_source_label"`. Review generated SQL -- should be two `ADD COLUMN ... DEFAULT 0` on `connection` plus one `ADD COLUMN` on `contact_source`. No data migration needed.

- **Frontend consideration:** The contact import UI (when built) should present a dropdown or radio for `source_label` when uploading a contacts CSV. Values: "Personal Gmail", "Work Gmail", "iCloud", "Office 365". Maps to the enum values above. Until the frontend exists, CLI import scripts should accept `--source-label` as a required flag.

- Update the data model spec (`linkedout_data_model.collab.md`) connection table definition to include the new columns. Delegate: `/taskos-update-spec` -- add `affinity_external_contact FLOAT NOT NULL DEFAULT 0` and `affinity_embedding_similarity FLOAT NOT NULL DEFAULT 0` to the connection table definition. Review output for accuracy.

- Run repository wiring tests to confirm entity still works with SQLite (unit) and PostgreSQL (integration).

**Design review:**
- Spec consistency (Data Model): Adding columns to `connection` follows the pattern established by V1 signal columns (`affinity_source_count`, `affinity_recency`, etc.). Column naming follows `affinity_{signal_name}` convention.
- Naming: `affinity_external_contact` and `affinity_embedding_similarity` match the spec's signal names. Considered `affinity_contact_warmth` but `external_contact` is the term used throughout the spec and high-level plan.
- Migration safety: `ADD COLUMN ... DEFAULT 0` is a metadata-only operation in PostgreSQL 11+ (no table rewrite). Safe for 24K+ connection rows.
- The existing `affinity_mutual_connections` column (placeholder at 0.0) stays -- it's documented in the spec's "Not Included" section as deferred.

## Sub-phase 2: Company-Size Normalized Career Overlap

**Outcome:** `_compute_career_overlap` is replaced with a company-size-aware version that uses `log2(employee_count + 2)` dampening and temporal overlap (months of concurrent employment). Sharing a 10-person startup scores dramatically higher than both having worked at Google. The old Jaccard set-overlap is gone. Unit tests validate the size-factor math and temporal overlap logic. The spec's `[Planned] Company-size normalized career overlap` behavior is implemented.

**Dependencies:** Sub-phase 1 (new columns exist, but this sub-phase changes scoring logic that touches career_overlap column which already exists)

**Estimated effort:** 1.5 sessions (~3-4 hours)

**Verification:**
- `pytest tests/unit/intelligence/test_affinity_scorer.py -v` -- all existing tests updated + new tests pass
- New unit tests specifically verify:
  - `size_factor(10)` >> `size_factor(50000)` (small company scores much higher)
  - `size_factor(None)` uses default of 500 (matching old script's fallback)
  - `overlap_months` correctly computes concurrent employment months
  - `overlap_months` handles None start_date (returns 0.0)
  - `overlap_months` handles None end_date (treats as "Present" = today)
  - Full career overlap with size normalization: two people at a 10-person company for 24 months scores ~0.6+, two people at a 50K company for 24 months scores ~0.1
  - Career overlap still returns 0.0 when user has no own_crawled_profile_id
  - Career overlap still returns 0.0 when either side has no experiences
  - Normalization cap: `min(total / 36.0, 1.0)` ensures score is bounded 0-1

Key activities:

- **Port `size_factor()` and `overlap_months()` as module-level pure functions** in `affinity_scorer.py`. Translate directly from `<prior-project>/linkedin-intel/scripts/compute_affinity.py` (lines 23-36). Key formula: `1.0 / log2((employee_count or 500) + 2)` where 500 is the fallback for NULL employee_count.

- **Rewrite `_compute_career_overlap()`** to accept experience-level data (with dates and company sizes) instead of just company ID sets. New signature:
  ```python
  def _compute_career_overlap(
      connection_experiences: list[dict],  # [{company_id, start_date, end_date}]
      user_experiences: list[dict],        # [{company_id, start_date, end_date}]
      company_sizes: dict[str, int],       # {company_id: estimated_employee_count}
  ) -> float:
  ```
  Logic: for each pair of (user_exp, connection_exp) with matching company_id, compute `overlap_months * size_factor(employee_count)`, sum all, then `min(total / 36.0, 1.0)`. This matches the old script exactly.

- **Update `_batch_fetch_connection_companies()`** to return experience-level data (company_id + start_date + end_date) instead of just company ID sets. Similarly update `_get_user_companies()` to return experience dicts.

- **Add a new batch query `_batch_fetch_company_sizes()`** that loads `{company_id: estimated_employee_count}` for all companies referenced by any connection or user experience. Single query: `SELECT id, estimated_employee_count FROM company WHERE id = ANY(:ids)`.

- **Update `compute_for_user()`** to pass the new data structures to `_compute_career_overlap()`. The batch fetch pattern stays (one query per data type), just the data shape changes.

- **Update `compute_for_connection()`** similarly -- fetch experience-level data for the single connection.

- **Update all existing unit tests** that test `_compute_career_overlap`. The old tests used set-based inputs (`{'c1', 'c2'}`); they need to use experience dict lists. Rewrite with equivalent logic but the new data shape. The `_make_experience` test helper needs to include start_date/end_date.

- **Add new unit tests** for `size_factor()`, `overlap_months()`, and the normalized career overlap (see verification above for specific cases).

- **Integration test update:** The `intelligence_test_data` fixture needs to include start_date/end_date on experiences and employee_count on companies. Update `test_affinity_integration.py` to verify career overlap still produces nonzero values for shared companies.

**Design review:**
- Spec consistency (Affinity Scoring spec, V2 Planned): "overlap_months * size_factor, normalized by min(total / 36.0, 1.0)" -- implementation matches exactly.
- Spec consistency (Affinity Scoring spec, V2 Planned): "log2(employee_count + 2) dampening" -- matches `size_factor()` formula. The spec says `log2(employee_count + 2)` but the old script uses `1.0 / log2(...)` (inverse). The dampening IS the inverse -- larger companies produce smaller factors. The spec description is slightly ambiguous; implementation should use the inverse (`1.0 / log2(...)`) to match the old script's proven behavior.
- Architecture: Changing `_compute_career_overlap` signature is a breaking change for tests but not for external consumers (it's a private function). The class interface (`compute_for_user`, `compute_for_connection`) is unchanged.
- Error paths: What if `company.estimated_employee_count` is NULL for a shared company? The `size_factor()` function uses `(employee_count or 500) + 2` -- defaults to 500 (mid-size assumption). This matches the old script.
- Error paths: What if experiences have no start_date? `overlap_months` returns 0.0. That experience pair contributes nothing to the score. This is correct -- no temporal data means no overlap signal.
- Performance: The new `_batch_fetch_company_sizes()` is one additional query per `compute_for_user` call. With ~3K companies this is negligible. No N+1 risk.

## Sub-phase 3a: External Contact Signal

**Outcome:** Connections confirmed through external contact sources (Google Contacts, phone contacts) receive a warmth bonus stored in `affinity_external_contact`. The signal uses `contact_source` rows linked to connections via `contact_source.connection_id`. Phone contacts score higher (1.0) than email-only (0.7). Multiple external sources stack but cap at 1.0. When `contact_source` has 0 rows (current state), all connections get 0.0 for this signal. The spec's `[Planned] External contact signal` behavior is implemented.

**Dependencies:** Sub-phase 1 (new column exists)

**Estimated effort:** 1 session (~2-3 hours)

**Verification:**
- Unit tests verify:
  - `_compute_external_contact_score([])` returns 0.0
  - Connection with one email-only contact_source returns 0.7
  - Connection with one phone contact_source returns 1.0
  - Connection with both email and phone returns 1.0 (phone dominates)
  - Connection with multiple email-only sources still caps at 0.7 (email ceiling) -- OR stacks? Decision needed (see Open Questions)
  - Source types other than known external sources (e.g., `linkedin_csv`) contribute 0.0
- Integration test: With `contact_source` table having 0 rows, all connections get `affinity_external_contact = 0.0`
- `affinity_external_contact` column is populated after `compute_for_user`

Key activities:

- **Define `_compute_external_contact_score()` pure function** in `affinity_scorer.py`. Input: list of contact source records for a connection (source_type, has_phone, has_email). Logic:
  - Filter to external source types: `google_contacts_job`, `gmail_email_only`, `contacts_phone` (extensible list as a module constant `EXTERNAL_SOURCE_TYPES`). These are the actual converter `source_type` values in the codebase — `linkedin_csv` is excluded since it's the base network data, not an external contact signal.
  - If no external sources match: return 0.0
  - If any source has phone: return 1.0
  - If any source has email (but no phone): return 0.7
  - This is simpler than the old `enrich_affinity_gmail.py` which used RapidFuzz name matching because the new schema already links `contact_source` to `connection` via `contact_source.connection_id` (dedup pipeline resolves this). No fuzzy matching needed in the scorer -- that's the import pipeline's job.

- **Add batch query `_batch_fetch_external_contacts()`** to `AffinityScorer`. Query:
  ```sql
  SELECT cs.connection_id, cs.source_type, cs.phone, cs.email
  FROM contact_source cs
  WHERE cs.connection_id = ANY(:connection_ids)
    AND cs.source_type IN ('google_contacts_job', 'gmail_email_only', 'contacts_phone')
    AND cs.dedup_status = 'matched'
  ```
  Returns `dict[str, list[dict]]` keyed by connection_id. This is one query per `compute_for_user` call.

- **Wire into `compute_for_user()` and `compute_for_connection()`**. For each connection, call `_compute_external_contact_score()` with its contact sources. Store result in `conn.affinity_external_contact`.

- **Unit tests** for the pure function (see verification above). Use simple dict inputs, no DB.

- **Integration test**: Verify that with an empty `contact_source` table, all connections get `affinity_external_contact = 0.0`. Add a test case where a contact_source row is created linked to a connection, and verify the signal becomes nonzero.

- **Note: `contact_source` currently has 0 rows in production.** This signal will produce 0.0 for all connections until a Google Contacts CSV import is done. This is expected and documented in the spec's edge cases. The implementation is forward-looking -- it's ready when the data arrives.

**Design review:**
- Spec consistency (Affinity Scoring spec, V2 Planned): "Phone contacts score higher than email-only" -- implementation uses 1.0 for phone, 0.7 for email-only. These thresholds are not in the spec -- they're a design choice. Document them as constants.
- Spec consistency (Data Model spec, contact_source): `connection_id` is nullable (pending dedup). The query filters `dedup_status = 'matched'` which ensures only resolved links are used. Correct.
- Naming: `EXTERNAL_SOURCE_TYPES` constant makes the extensibility explicit. Current values (`google_contacts_job`, `gmail_email_only`, `contacts_phone`) match the actual converter source_type values. Adding new sources later is a one-line change.
- Security: No user input in the query. All parameterized. No concerns.
- Error paths: What if `contact_source.connection_id` is NULL (pending dedup)? The `WHERE cs.connection_id = ANY(...)` naturally excludes NULLs. No issue.
- Architecture: The old `enrich_affinity_gmail.py` used RapidFuzz fuzzy matching to link Gmail contacts to profiles. In the new schema, this linkage is handled by the import pipeline's dedup system (`contact_source.connection_id`). The scorer just reads the resolved links. This is a cleaner separation of concerns.

## Sub-phase 3b: Embedding Similarity Signal

**Outcome:** Cosine similarity between the user's own profile embedding (1536-dim) and each connection's profile embedding is computed and stored in `affinity_embedding_similarity`. Returns 0.0 when either embedding is missing. The spec's `[Planned] Embedding similarity signal` behavior is implemented.

**Dependencies:** Sub-phase 1 (new column exists)

**Estimated effort:** 1 session (~2-3 hours)

**Verification:**
- Unit tests verify:
  - `_compute_embedding_similarity(None, embedding)` returns 0.0
  - `_compute_embedding_similarity(embedding, None)` returns 0.0
  - `_compute_embedding_similarity(vec_a, vec_b)` returns known cosine similarity (hand-computed)
  - Result is bounded 0-1 (cosine similarity of normalized vectors)
- Integration test: User with `own_crawled_profile_id` set and profile with embedding -- verify connections with embeddings get nonzero `affinity_embedding_similarity`
- Integration test: User without `own_crawled_profile_id` -- all connections get 0.0

Key activities:

- **Define `_compute_embedding_similarity()` pure function** in `affinity_scorer.py`. Input: two optional embedding vectors (list[float] or None). Logic:
  - If either is None: return 0.0
  - Compute cosine similarity: `dot(a, b) / (norm(a) * norm(b))`
  - Clamp to [0.0, 1.0] (negative cosine similarity means anti-correlated; treat as 0 for affinity purposes)
  - Use numpy for efficiency if available, otherwise pure Python (numpy is already a dependency via pgvector). Check project dependencies first.

- **Add user embedding fetch to `_get_user_companies()` or create `_get_user_embedding()`**. Query the user's own `crawled_profile.embedding` via `app_user.own_crawled_profile_id`. Return the embedding vector or None.

- **Add batch query `_batch_fetch_connection_embeddings()`**. Query:
  ```sql
  SELECT c.id, cp.embedding
  FROM connection c
  JOIN crawled_profile cp ON c.crawled_profile_id = cp.id
  WHERE c.app_user_id = :app_user_id
    AND cp.embedding IS NOT NULL
  ```
  Returns `dict[str, list[float]]` keyed by connection_id.

- **Wire into `compute_for_user()` and `compute_for_connection()`**. If user embedding is None, skip (all connections get 0.0 for this signal). Otherwise compute similarity for each connection.

- **Performance consideration:** Loading 24K embeddings at 1536 dimensions is ~144MB of float data. This may be too much for a single batch query. Consider chunking the batch fetch (e.g., 1000 connections at a time) or using pgvector's built-in cosine distance operator (`<=>`) to compute in the DB instead of in Python. The DB approach is likely faster and avoids memory pressure.

  **Preferred approach:** Use pgvector's `<=>` operator in a single SQL query:
  ```sql
  SELECT c.id, 1 - (cp.embedding <=> :user_embedding) AS similarity
  FROM connection c
  JOIN crawled_profile cp ON c.crawled_profile_id = cp.id
  WHERE c.app_user_id = :app_user_id
    AND cp.embedding IS NOT NULL
  ```
  This computes cosine similarity in the DB, returns only the float score per connection, and is significantly more memory-efficient. Falls back to 0.0 for connections without embeddings (excluded by WHERE clause, handled in Python).

- **Unit tests** for the pure function using small hand-crafted vectors. Test zero vectors, identical vectors (similarity=1.0), orthogonal vectors (similarity=0.0).

- **Integration test**: Create test profiles with embeddings (can be short dummy vectors for testing), verify similarity is computed and stored.

- **Spec note:** The spec says "768-dim nomic vectors" but the entity has `Vector(1536)`. The spec needs a correction. Add a note to update the spec in Sub-phase 4.

**Design review:**
- Spec consistency (Affinity Scoring spec, V2 Planned): "Cosine similarity between user's own profile embedding and each connection's" -- implementation matches. "0.0 when either embedding is missing" -- matches.
- Spec inconsistency: Spec says "768-dim nomic vectors" but `crawled_profile.embedding` is `Vector(1536)`. The actual dimension in the DB is the source of truth. Flag for spec update.
- Architecture: Using pgvector's `<=>` operator keeps the heavy computation in the DB where the data already lives. This is the idiomatic pgvector pattern and avoids transferring 144MB of vector data to Python.
- Performance: With pgvector index (`ivfflat` or `hnsq`), the cosine distance query is efficient even for 24K rows. Without an index, it's a sequential scan -- still fast for 24K but worth monitoring. An index is NOT needed for batch recomputation (we're computing ALL pairs, not searching for nearest neighbors).
- Error paths: If the user's own profile has no embedding (not yet generated), all connections get 0.0. This is correct and expected.
- SQLite compatibility for unit tests: The `<=>` operator is PostgreSQL-only. Unit tests for the pure function should use Python-side cosine similarity. The DB-side computation is tested via integration tests only.

## Sub-phase 4: V2 Weight Revision and Formula Integration

**Outcome:** All five signals are combined with V2 weights into the final affinity score. The formula is: `career_overlap * W_CO + external_contact * W_EC + embedding_similarity * W_ES + source_count * W_SC + recency * W_R` where weights sum to 1.0. `AFFINITY_VERSION` is bumped to 2. Recomputing affinity for all users produces V2 scores. Dunbar tiers are reassigned based on V2 scores.

**Dependencies:** Sub-phase 2, Sub-phase 3a, Sub-phase 3b (all signals must be implemented)

**Estimated effort:** 1 session (~2 hours)

**Verification:**
- `AFFINITY_VERSION == 2` in the module
- V2 weights are defined as module constants and sum to 1.0
- `_compute_affinity()` accepts all 5 signal values
- Unit test: `_compute_affinity(1.0, 1.0, 1.0, 1.0, 1.0)` returns 100.0
- Unit test: known-value test with specific inputs produces expected score
- Integration test: `compute_for_user` populates all signal columns including the two new ones
- `rcv2 db compute-affinity` runs successfully, all connections have `affinity_version = 2`
- All existing tests updated to use V2 weights/signatures and pass
- `precommit-tests` pass

Key activities:

- **Define V2 weight constants** in `affinity_scorer.py`. Based on the spec's guidance ("career_overlap dominant ~0.4-0.5, external_contact ~0.2-0.3, embedding_similarity ~0.15-0.2, source_count and recency reduced"):
  ```python
  # V2 weights
  WEIGHT_CAREER_OVERLAP = 0.40
  WEIGHT_EXTERNAL_CONTACT = 0.25
  WEIGHT_EMBEDDING_SIMILARITY = 0.15
  WEIGHT_SOURCE_COUNT = 0.10
  WEIGHT_RECENCY = 0.10
  ```
  These sum to 1.0. Career overlap is dominant. Source count and recency are demoted from 0.375 each to 0.10 each -- they're low-fidelity signals that reflected data availability more than relationship strength.

  **Note:** Final weights are marked TBD in the spec. These are initial values based on the spec's guidance ranges. They should be tuned after running V2 on real data and inspecting the score distribution. The weights are module constants that are trivial to adjust.

- **Update `_compute_affinity()` signature** to accept all 5 signals:
  ```python
  def _compute_affinity(
      source_count_norm: float, recency: float, career_overlap: float,
      external_contact: float, embedding_similarity: float,
  ) -> float:
  ```

- **Update `compute_for_user()` and `compute_for_connection()`** to pass all 5 signals to `_compute_affinity()` and store the two new breakdown columns.

- **Bump `AFFINITY_VERSION` to 2.** This allows distinguishing V1 and V2 scored connections.

- **Update all unit tests** that call `_compute_affinity()` to pass the new arguments. Update expected scores to reflect V2 weights.

- **Update integration tests** to check that all 7 signal/metadata columns are populated (affinity_source_count, affinity_recency, affinity_career_overlap, affinity_external_contact, affinity_embedding_similarity, affinity_computed_at, affinity_version=2).

- **Update the affinity scoring spec** (`linkedout_affinity_scoring.collab.md`): promote V2 planned behaviors to the main Behaviors section, update the formula, add the actual weight values, correct the embedding dimension from 768 to 1536, bump version to 2. Delegate: `/taskos-update-spec` with the changes. Review output for accuracy.

- **Update the data model spec** (`linkedout_data_model.collab.md`): fix the stale V1 formula comment (currently shows `0.3/0.3/0.2/0.2` with mutual_connections, should reflect V2 weights `0.40/0.25/0.15/0.10/0.10`). Delegate: `/taskos-update-spec`. This ensures both the affinity scoring spec and data model spec are consistent with V2.

- **Run `precommit-tests`** to verify nothing is broken.

- **Run `rcv2 db compute-affinity`** against the dev database to verify V2 scoring end-to-end. Compare distribution against V1 scores -- career overlap should now be the dominant factor, connections at small shared companies should rank higher.

**Design review:**
- Spec consistency: All five V2 planned behaviors are now implemented and promoted to main behaviors. No planned behaviors remain.
- Spec update needed: Embedding dimension correction (768 -> 1536). Weight values need to be added to spec.
- Naming: Weight constants follow `WEIGHT_{SIGNAL_NAME}` pattern, matching V1 style.
- Architecture: The scoring formula remains a simple weighted sum scaled to 0-100. No architectural changes. The class interface is unchanged (`compute_for_user`, `compute_for_connection`).
- Error paths: If all new signals return 0.0 (no contact_source rows, no embeddings, no temporal overlap data), V2 degrades to source_count * 0.10 + recency * 0.10 = max 20 points. This is correct -- sparse data should produce low affinity scores. The old V1 max with just source_count + recency was 75 points; V2 caps at 20 for the same data. This is intentional -- V2 rewards richer data.
- Backward compatibility: V1 scores are overwritten. The `affinity_version` column distinguishes V1 vs V2 if historical comparison is needed. No rollback mechanism beyond re-running V1 code (which is in git history).

## Build Order

```
Sub-phase 1 (Schema Migration) ──┬──> Sub-phase 2 (Career Overlap V2) ──┐
                                  ├──> Sub-phase 3a (External Contact)  ──┼──> Sub-phase 4 (V2 Weights + Integration)
                                  └──> Sub-phase 3b (Embedding Sim)    ──┘
```

**Critical path:** Sub-phase 1 -> Sub-phase 2 -> Sub-phase 4 (career overlap is the most complex signal and drives the most test changes)

**Parallelism:** Sub-phases 2, 3a, and 3b can run in parallel after Sub-phase 1. They touch different signals and different data sources. However, Sub-phase 2 changes the `_compute_career_overlap` signature which Sub-phase 4 consumes, making it the gating sub-phase.

**Recommended execution order (serial, practical):** 1 -> 2 -> 3a -> 3b -> 4. Serial is simpler for a single developer, and the total effort is ~4-5 sessions.

### Cross-Phase Execution Order

This is **Phase 3 of 3**. Runs after Phase 2 (Company Enrichment) so that company-size normalized career overlap has real `estimated_employee_count` data from Day 1 — no fallback defaults needed. After completion, run `compute-affinity` (V2) and do an eyeball session on top-50 to validate weights.

**Prerequisite gates:** Phase 1 Sub-phase 4 (V1 Pipeline Gate) passed. Phase 2 completed successfully.

```
Phase 1: Classify Roles ──> V1 Pipeline GATE ──> Phase 2: Company Enrichment ──> Phase 3: Affinity V2 ──> Run V2 + Eyeball Session
                                                                                       ^^^^ YOU ARE HERE
```

## Design Review Flags

| Sub-phase | Flag | Action |
|-----------|------|--------|
| Sub-phase 2 | Spec says `log2(employee_count + 2)` dampening but old script uses inverse `1.0 / log2(...)` -- the inverse IS the dampening | Use `1.0 / log2((employee_count or 500) + 2)` matching old script. Clarify in spec update. |
| Sub-phase 3a | Phone vs email score thresholds (1.0 vs 0.7) are not in the spec -- design choice | RESOLVED: Spec updated with cap-at-highest-tier policy. Phone=1.0, email=0.7, no stacking. |
| Sub-phase 3b | Spec says "768-dim nomic vectors" but entity has `Vector(1536)` | RESOLVED: Spec corrected to 1536-dim text-embedding-3-small. |
| Sub-phase 4 | V2 weights are initial values -- spec says "Final weights TBD after signal analysis" | RESOLVED: Spec updated with concrete weights (0.40/0.25/0.15/0.10/0.10). Eyeball session after first run. |
| Sub-phase 4 | V2 scores will be significantly different from V1 -- connections scored under V1 get overwritten | Acceptable: `affinity_version` column distinguishes them. No downstream consumer depends on absolute score values; Dunbar tiers are rank-based and adapt automatically. |

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Company `estimated_employee_count` is NULL for most companies (not yet enriched) | High -- career overlap degrades to default size_factor(500) for all companies, losing the small-company advantage | Check: `SELECT COUNT(*) FROM company WHERE estimated_employee_count IS NOT NULL`. If <10%, the signal is mostly noise. Mitigation: this plan depends on Phase 2 (company enrichment) running first to populate employee counts. If not done, career overlap V2 still works but with less discrimination than intended. |
| `contact_source` has 0 rows -- external contact signal is dead weight | Low -- the signal produces 0.0 for all connections, reducing V2 to effectively 4 signals | Expected and documented. The signal is forward-looking. No wasted computation (batch query returns empty result fast). |
| Experience rows lack start_date/end_date (Apify sometimes doesn't extract dates) | Med -- temporal overlap returns 0.0 for those pairs, making career overlap depend only on date-having experiences | Check: `SELECT COUNT(*) FROM experience WHERE start_date IS NOT NULL`. If most experiences have dates, impact is low. If few do, career overlap V2 is no better than V1 for most connections. |
| Embedding computation for 24K profiles is expensive (pgvector cosine distance) | Low -- pgvector `<=>` operator is optimized, 24K sequential comparisons against one vector takes <1s | Monitor timing. If >10s, consider adding a pgvector index (HNSW). |
| V2 scores break downstream assumptions | Low -- Dunbar tiers are rank-based (adapt automatically). Search agent uses tiers, not raw scores. No UI displays raw scores currently. | Verify search agent doesn't threshold on absolute scores. |

## Open Questions

- **External contact stacking policy:** ~~RESOLVED~~ Cap at highest-tier signal per connection: phone in any source → 1.0, email-only (any number of sources) → 0.7, no contact_source rows → 0.0. Multiple sources don't stack. `contact_source.source_label` tracks origin (google_personal, google_work, icloud, office365) for import traceability but does not affect scoring. Frontend import UI should present source_label as a required dropdown; CLI imports use `--source-label` flag.

- **V2 weight tuning:** ~~RESOLVED~~ Yes, eyeball session after first V2 run. Query top-50 ranked connections, check if ranking feels right. Weights (0.40/0.25/0.15/0.10/0.10) ship as constants in scorer, easy to tweak. No config system. Spec updated.

- **Company enrichment dependency:** ~~RESOLVED~~ Yes, Phase 3 runs AFTER Phase 2. Execution order: Phase 1 → V1 pipeline → Phase 2 (company enrichment) → Phase 3 (affinity V2). This gives career overlap V2 real employee_count data from Day 1.

- **Embedding model dimension:** ~~RESOLVED~~ DB has 1536-dim vectors, generated by OpenAI `text-embedding-3-small` (not nomic 768-dim). Spec already corrected to "1536-dim text-embedding-3-small vectors".

## Spec References

| Spec | Sections Referenced | Conflicts Found |
|------|---------------------|-----------------|
| `linkedout_affinity_scoring.collab.md` | V2 Planned Enhancements (all 4 items), Decisions > Company-size normalization, Decisions > V2 weight rebalancing | 1 -- Embedding dimension stated as 768 but entity/DB uses 1536. Fix in Sub-phase 4. |
| `linkedout_data_model.collab.md` | Table Overview > connection, contact_source, company, experience, crawled_profile | 1 -- connection table needs two new columns added to spec (Sub-phase 1 activity). |
| `cli_commands.collab.md` | DB Group > compute-affinity | None -- CLI interface unchanged, just scoring logic behind it. |

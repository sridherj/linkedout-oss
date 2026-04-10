# Cross-Phase Plan Review Findings

**Reviewed:** 2026-03-28
**Reviewer:** taskos-plan-review agent
**Plans reviewed:**
1. `2026-03-28-classify-roles-port-and-wiring.md` (Phase 1)
2. `2026-03-28-company-enrichment-port.md` (Phase 2)
3. `2026-03-28-affinity-v2-enhancements.md` (Phase 3)

**Specs cross-checked:**
- `linkedout_affinity_scoring.collab.md` (v1)
- `linkedout_data_model.collab.md` (v5)
- `cli_commands.collab.md` (v2)
- `linkedout_intelligence.collab.md` (v3)
- `_registry.md`

---

## Task A: Item -> Phase Rename

**Status: COMPLETE.** All occurrences of "Item 1/2/3" and "Cross-Item" have been replaced with "Phase 1/2/3" and "Cross-Phase" across all three plan files. Verified with grep -- zero remaining "Item [123]" matches.

---

## Section 1: Architecture

### Issue #1: Data model spec V1 formula is inconsistent with code and affinity scoring spec

The data model spec (`linkedout_data_model.collab.md`, line ~494-500) states the V1 formula as:
```
affinity_source_count * 0.3 + affinity_recency * 0.3 + affinity_mutual_connections * 0.2 + affinity_career_overlap * 0.2
```

But the actual code (`affinity_scorer.py`) and the affinity scoring spec both use:
```
source_count * 0.375 + recency * 0.375 + career_overlap * 0.25
```

The data model spec includes `mutual_connections` with weight 0.2, but that signal is a placeholder (always 0.0) and not used in the formula. The weights also differ (0.3/0.3/0.2/0.2 vs 0.375/0.375/0.25).

**Impact:** Plan 3 Sub-phase 4 changes the formula to V2 weights. If someone reads the data model spec, they'll see stale V1 weights that don't match the code. This could cause confusion during implementation.

**Recommendation:** Update the data model spec's V1 formula section to match the actual code (0.375/0.375/0.25, no mutual_connections). Plan 3 Sub-phase 4 already plans to update the affinity scoring spec with V2 values, but the data model spec's formula comment also needs updating. Add this as an activity in Phase 3 Sub-phase 4.

### Issue #2: Cross-phase dependency chain is correct and explicit

The three phases build on each other correctly:
```
Phase 1 (classify-roles) -> V1 Pipeline -> Phase 2 (company enrichment) -> Phase 3 (affinity V2)
```

- Phase 1 has no external dependencies. Its output (populated `role_alias` table) enables `backfill-seniority`, which enables V1 `compute-affinity`.
- Phase 2 depends on Phase 1 completion only implicitly (the V1 pipeline must run first for baseline scores). Phase 2's direct output (`estimated_employee_count` on companies) is required by Phase 3's `size_factor()`.
- Phase 3 depends on Phase 2 for real employee count data.

**No issues found.** Dependencies are explicit, correct, and documented in each plan's Cross-Phase Execution Order section.

### Issue #3: Plan 3 Sub-phase 3a external contact query references `source_type` values that don't match existing code

Plan 3 Sub-phase 3a defines `EXTERNAL_SOURCE_TYPES = ['google_contacts', 'office_contacts', 'icloud_contacts']` and queries `contact_source WHERE source_type IN (...)`.

But the actual `source_type` values in the codebase (from converter classes) are:
- `linkedin_csv`
- `google_contacts_job`
- `gmail_email_only`
- `contacts_phone`

None of these match the plan's `google_contacts`, `office_contacts`, `icloud_contacts`. The plan appears to use hypothetical future source types rather than the ones that actually exist.

**Impact:** When Phase 3 Sub-phase 3a is implemented, the `EXTERNAL_SOURCE_TYPES` list won't match any real data, making the query return empty even when contact_source has Google Contacts data. This is a silent correctness bug.

**Recommendation:** Update Plan 3 Sub-phase 3a to use the actual converter `source_type` values. The external source type list should be `['google_contacts_job', 'gmail_email_only', 'contacts_phone']` (all the non-LinkedIn converters). `linkedin_csv` is NOT an external contact source since it's the base network data. Keep the plan's extensible constant approach, but populate it with real values.

### Issue #4: Plan 3 Sub-phase 3a `source_label` column addition -- is it needed now?

Plan 3 Sub-phase 1 adds a `source_label` column to `contact_source` for distinguishing `google_personal` vs `google_work` etc. But `contact_source` already has `source_type` which distinguishes import origins. The `source_label` adds a second dimension (which account within a source type).

Given that `contact_source` currently has 0 rows and the import pipeline isn't built yet for non-LinkedIn sources, adding `source_label` is forward-looking infrastructure with no immediate consumer.

**Impact:** Low. It's a nullable column addition -- cheap to add, cheap to ignore.

**Recommendation:** Keep it. The column is free (nullable, no migration cost), and it's documented in the spec's decisions. If it's dropped from the migration now, someone will need to add it later when the import UI is built. The plan already notes it's forward-looking.

---

## Section 2: Code Quality

### Issue #5: Plan 2 Sub-phase 3 resolved PDL CSV reading to use `csv.DictReader` but risk table still says pandas

The Design Review Flags table for Plan 2 Sub-phase 3 has an entry: "PDL file path default needs adaptation" and notes `pandas` is used for chunked CSV reading. The Open Questions section resolves this to `csv.DictReader` (no pandas). However, the Key Risks table still says: "The old script uses chunked pandas read (500K rows/chunk) which is proven fast. Keep the same approach."

**Impact:** Contradictory guidance. An executing agent might install pandas based on the risk table, or might use csv.DictReader per the resolution. The risk table's performance claim ("proven fast") doesn't apply to csv.DictReader which will be slower for a 2GB file.

**Recommendation:** Update the Key Risks table entry for PDL CSV file to reflect the resolved approach: "Uses `csv.DictReader` with `itertools.islice` chunking. First run may take 5-10 minutes for a 2GB file. Monitor timing." Remove the pandas reference.

### Issue #6: Phase 1 and Phase 2 both delegate spec updates to `/taskos-update-spec` -- correct pattern

Both plans explicitly say "Delegate: `/taskos-update-spec`" when updating specs. This matches the Claude Code skill delegation pattern (the skill exists in the system prompt). Good.

**No action needed.**

### Issue #7: SQL patterns are consistent across all three phases

All three plans correctly use:
- `sqlalchemy.text()` with `:param` named parameters (not `%s`)
- `db_session_manager.get_session(DbSessionType.WRITE)` for write sessions
- Raw SQL for bulk operations (appropriate for dev_tools batch scripts)
- `Nanoid.make_nanoid_with_prefix()` for ID generation in raw SQL inserts

**No issues found.**

---

## Section 3: Tests

### Issue #8: Phase 2 has NO integration or unit tests planned for `enrich_companies.py` itself

Phase 2 Sub-phase 2 has unit tests for utility functions (`company_utils.py`, `wikidata_utils.py`) and a live service test for Wikidata. Sub-phase 3 (the core enrichment script) has NO test activities listed. The verification is entirely manual (run CLI, check psql output).

Sub-phase 4 says "Run `precommit-tests` to confirm nothing is broken" -- but there are no tests FOR the enrichment script itself. The only test coverage is for the utility functions and the live Wikidata API.

**Impact:** The core enrichment logic (PDL matching, COALESCE UPDATE pattern, idempotency, dry-run behavior) is untested. If a bug is introduced (e.g., wrong COALESCE column order, missing enrichment_sources append), it won't be caught until manual inspection.

**Recommendation:** Add integration test activities to Phase 2 Sub-phase 3 or Sub-phase 4:
- Test that `main(dry_run=True)` reads but writes nothing (verify DB unchanged)
- Test that `main(dry_run=False)` with a small test fixture (3-5 companies, mock PDL CSV) populates the expected columns
- Test idempotency: running twice produces same result
- Test COALESCE semantics: pre-existing data is NOT overwritten

This doesn't need to be a large test suite. Even 3-4 integration tests against the test PostgreSQL would catch the most dangerous bugs.

### Issue #9: Phase 1 test coverage is thorough

75 parametrized unit tests for pure functions, plus manual E2E verification via CLI. The pure function tests are the right layer (unit) for regex classification. DB operations are verified via CLI + psql spot-checks, which is acceptable for a dev_tools batch script.

**No issues found.**

### Issue #10: Phase 3 test plan is comprehensive

Phase 3 has unit tests for each new pure function (`size_factor`, `overlap_months`, `_compute_embedding_similarity`, `_compute_external_contact_score`), updated existing unit tests for the changed `_compute_career_overlap` signature, and integration test updates to verify all 7 signal columns. The test plan covers edge cases (None embeddings, None start_dates, zero contact_source rows, size_factor default fallback).

**No issues found.** The Phase 3 test plan is the strongest of the three.

---

## Section 4: Performance

### Issue #11: Phase 2 Wikidata rate limiting -- 0.3s delay with 500 companies = 2.5 minutes minimum

The plan correctly limits Wikidata searches to 500 per run with 0.3s delay between searches. This means 500 * 0.3s = 150 seconds minimum for the Wikidata phase, plus SPARQL batch queries. Total Wikidata phase: ~3-5 minutes per run.

With 47K companies, reaching full Wikidata coverage would require ~94 runs. The plan handles this via the `--wikidata-limit N` flag, but the magnitude should be documented.

**Impact:** Low. Wikidata is supplementary (PDL is primary). The plan correctly separates PDL and Wikidata transactions so PDL results are committed even if Wikidata is slow/fails.

**Recommendation:** No code change needed. The plan could add a note: "Full Wikidata coverage of all 47K companies is impractical (would require ~94 runs at 500/run). In practice, target the top-N companies by `network_connection_count` (already implemented via ORDER BY in the query). ~500-1000 companies covers the most valuable network nodes."

### Issue #12: Phase 3 embedding similarity -- pgvector `<=>` approach is correct

The plan correctly identifies that loading 24K embeddings (144MB) into Python is wasteful and proposes using pgvector's `<=>` operator in SQL instead. The plan also notes that a pgvector index (HNSW) is NOT needed for batch recomputation (computing ALL pairs, not nearest-neighbor search).

**No issues found.** This is the right approach.

### Issue #13: Phase 1 batch sizes are reasonable

Phase 1 Sub-phase 2 batches role_alias INSERTs in groups of 500-1000. With ~36K unique titles, this is 36-72 batches. The temp table approach for experience UPDATE replaces psycopg's COPY protocol with batched INSERT, which is slightly slower but fine for 40K rows.

**No issues found.**

---

## Section 5: Spec Consistency

### Issue #14: Affinity scoring spec V2 planned behaviors are well-aligned with Plan 3

Every `[Planned]` item in the affinity scoring spec maps to a specific sub-phase in Plan 3:
- External contact signal -> Sub-phase 3a
- Company-size normalized career overlap -> Sub-phase 2
- Embedding similarity signal -> Sub-phase 3b
- Revised V2 weight distribution -> Sub-phase 4

The spec's edge cases (0 contact_source rows, NULL embeddings, NULL own_crawled_profile_id) are all addressed in Plan 3's design review sections.

The embedding dimension inconsistency (spec originally said 768, corrected to 1536) is already marked as resolved in Plan 3 and confirmed in the spec.

**No issues found.**

### Issue #15: Data model spec missing `pdl_id` and `wikidata_id` on company table

The data model spec (`linkedout_data_model.collab.md`) does not include `pdl_id` or `wikidata_id` on the company table. Plan 2 Sub-phase 1 explicitly plans to add these columns and update the spec.

**No issues found.** The plan handles this correctly.

### Issue #16: Data model spec missing `affinity_external_contact` and `affinity_embedding_similarity` on connection table

The data model spec does not include the two new V2 signal columns. Plan 3 Sub-phase 1 plans to add them and update the spec.

**No issues found.** The plan handles this correctly.

### Issue #17: CLI commands spec needs updates from both Phase 1 and Phase 2

The CLI commands spec (`cli_commands.collab.md`, v2) needs:
- Phase 1: Add `db classify-roles` command
- Phase 2: Add `db enrich-companies` command

Both plans explicitly include spec update activities with `/taskos-update-spec` delegation. The behavior descriptions follow the established Given/Running/Verify format.

**No issues found.**

---

## Summary

| Section | Issues Found | Actionable | Informational |
|---------|-------------|------------|---------------|
| Architecture | 4 | 2 (#1, #3) | 2 (#2, #4) |
| Code Quality | 3 | 1 (#5) | 2 (#6, #7) |
| Tests | 3 | 1 (#8) | 2 (#9, #10) |
| Performance | 3 | 0 | 3 (#11, #12, #13) |
| Spec Consistency | 4 | 0 | 4 (#14-#17) |
| **Total** | **17** | **4** | **13** |

### Actionable Issues (require plan updates)

1. **#1 -- Data model spec V1 formula stale:** Add activity to Phase 3 Sub-phase 4 to update `linkedout_data_model.collab.md` formula comment alongside the affinity scoring spec update.

2. **#3 -- Wrong `EXTERNAL_SOURCE_TYPES` values in Phase 3:** Update Plan 3 Sub-phase 3a to use actual converter `source_type` values (`google_contacts_job`, `gmail_email_only`, `contacts_phone`) instead of hypothetical values (`google_contacts`, `office_contacts`, `icloud_contacts`).

3. **#5 -- Plan 2 contradictory PDL CSV reading guidance:** Update the Key Risks table in Plan 2 to remove the pandas reference and reflect the resolved `csv.DictReader` approach.

4. **#8 -- No tests for Phase 2 core enrichment script:** Add 3-4 integration tests for `enrich_companies.py` covering dry-run, basic enrichment, idempotency, and COALESCE semantics.

### Overall Assessment

The three plans are thorough, well-structured, and correctly sequenced. Cross-phase dependencies are explicit and consistent. SQL patterns match established codebase conventions. Spec references are accurate and updates are planned. The main gaps are: (a) a minor spec inconsistency in the data model, (b) wrong external source type values in Phase 3, (c) contradictory guidance in Phase 2's risk table, and (d) missing test coverage for Phase 2's core script. All four are straightforward to address.

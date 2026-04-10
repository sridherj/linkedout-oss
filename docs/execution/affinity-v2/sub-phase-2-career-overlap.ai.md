# Sub-Phase 2: Company-Size Normalized Career Overlap

**Goal:** linkedin-ai-production
**Phase:** 3 — Affinity V2 Enhancements
**Depends on:** SP-1 (Schema Migration)
**Estimated effort:** 1.5 sessions (~3-4h)
**Source plan section:** Sub-phase 2

---

## Objective

Replace the V1 Jaccard set-overlap `_compute_career_overlap` with a company-size-aware version using `log2(employee_count + 2)` dampening and temporal overlap (months of concurrent employment). Sharing a 10-person startup scores dramatically higher than both having worked at Google.

## Context

The old `_compute_career_overlap` uses set-based company overlap (Jaccard similarity). The new version ports proven logic from `<prior-project>/linkedin-intel/scripts/compute_affinity.py` (lines 23-36). The spec's `[Planned] Company-size normalized career overlap` behavior is implemented by this sub-phase.

## Tasks

1. **Add pure functions** `size_factor()` and `overlap_months()` as module-level functions in `affinity_scorer.py`:
   - `size_factor(employee_count)`: returns `1.0 / log2((employee_count or 500) + 2)` — smaller companies produce larger factors
   - `overlap_months(start_a, end_a, start_b, end_b)`: computes months of concurrent employment. Returns 0.0 if either start_date is None. Treats None end_date as today.

2. **Rewrite `_compute_career_overlap()`** with new signature:
   ```python
   def _compute_career_overlap(
       connection_experiences: list[dict],  # [{company_id, start_date, end_date}]
       user_experiences: list[dict],        # [{company_id, start_date, end_date}]
       company_sizes: dict[str, int],       # {company_id: estimated_employee_count}
   ) -> float:
   ```
   Logic: for each pair of (user_exp, connection_exp) with matching company_id, compute `overlap_months * size_factor(employee_count)`, sum all, then `min(total / 36.0, 1.0)`.

3. **Update `_batch_fetch_connection_companies()`** to return experience-level data (company_id + start_date + end_date) instead of just company ID sets. Similarly update `_get_user_companies()`.

4. **Add `_batch_fetch_company_sizes()`** batch query:
   ```sql
   SELECT id, estimated_employee_count FROM company WHERE id = ANY(:ids)
   ```
   Returns `{company_id: estimated_employee_count}`.

5. **Update `compute_for_user()` and `compute_for_connection()`** to pass new data structures to `_compute_career_overlap()`.

6. **Update all existing unit tests** for `_compute_career_overlap`. Rewrite from set-based inputs to experience dict lists.

7. **Add new unit tests** for:
   - `size_factor(10)` >> `size_factor(50000)` (small company scores much higher)
   - `size_factor(None)` uses default of 500
   - `overlap_months` correctly computes concurrent months
   - `overlap_months` handles None start_date (returns 0.0)
   - `overlap_months` handles None end_date (treats as today)
   - Full career overlap: two people at 10-person company for 24 months scores ~0.6+; two at 50K company for 24 months scores ~0.1
   - Career overlap returns 0.0 when user has no `own_crawled_profile_id`
   - Career overlap returns 0.0 when either side has no experiences
   - Normalization cap: `min(total / 36.0, 1.0)` bounds score to 0-1

8. **Update integration tests** — `intelligence_test_data` fixture needs start_date/end_date on experiences and employee_count on companies. Verify career overlap produces nonzero values for shared companies.

## Completion Criteria

- [ ] `size_factor()` and `overlap_months()` exist as pure module-level functions
- [ ] `_compute_career_overlap()` uses new signature with experience dicts + company sizes
- [ ] `_batch_fetch_connection_companies()` returns experience-level data
- [ ] `_batch_fetch_company_sizes()` added
- [ ] `compute_for_user()` and `compute_for_connection()` pass new data structures
- [ ] All existing career overlap tests updated and passing
- [ ] New unit tests for `size_factor`, `overlap_months`, normalized career overlap all pass
- [ ] Integration test updated and passing
- [ ] `pytest tests/unit/intelligence/test_affinity_scorer.py -v` all pass

## Verification

```bash
pytest tests/unit/intelligence/test_affinity_scorer.py -v -k "career_overlap or size_factor or overlap_months"
pytest tests/linkedout/intelligence/test_affinity_integration.py -v
```

## Design Notes

- **Spec vs old script:** Spec says `log2(employee_count + 2)` dampening. Old script uses `1.0 / log2(...)` (inverse). The dampening IS the inverse — larger companies produce smaller factors. Use the inverse.
- **NULL employee_count:** `size_factor()` uses `(employee_count or 500) + 2` — defaults to 500 (mid-size assumption).
- **NULL start_date:** `overlap_months` returns 0.0. No temporal data = no overlap signal.
- **Architecture:** `_compute_career_overlap` is a private function. Signature change is breaking for tests only, not external consumers.
- **Performance:** `_batch_fetch_company_sizes()` is one additional query per `compute_for_user` call. ~3K companies is negligible.

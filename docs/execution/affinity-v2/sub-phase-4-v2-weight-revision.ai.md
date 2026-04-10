# Sub-Phase 4: V2 Weight Revision and Formula Integration

**Goal:** linkedin-ai-production
**Phase:** 3 — Affinity V2 Enhancements
**Depends on:** SP-2 (Career Overlap V2), SP-3a (External Contact), SP-3b (Embedding Similarity)
**Estimated effort:** 1 session (~2h)
**Source plan section:** Sub-phase 4

---

## Objective

Combine all five signals with V2 weights into the final affinity score. Bump `AFFINITY_VERSION` to 2. Update specs. Verify end-to-end scoring.

## Context

After SP-2, SP-3a, and SP-3b, all five signals are implemented independently. This sub-phase wires them together with the V2 formula: `career_overlap * 0.40 + external_contact * 0.25 + embedding_similarity * 0.15 + source_count * 0.10 + recency * 0.10`.

## Tasks

1. **Define V2 weight constants** in `affinity_scorer.py`:
   ```python
   WEIGHT_CAREER_OVERLAP = 0.40
   WEIGHT_EXTERNAL_CONTACT = 0.25
   WEIGHT_EMBEDDING_SIMILARITY = 0.15
   WEIGHT_SOURCE_COUNT = 0.10
   WEIGHT_RECENCY = 0.10
   ```
   Weights sum to 1.0. Career overlap dominant. Source count and recency demoted from 0.375 each to 0.10.

2. **Update `_compute_affinity()` signature** to accept all 5 signals:
   ```python
   def _compute_affinity(
       source_count_norm: float, recency: float, career_overlap: float,
       external_contact: float, embedding_similarity: float,
   ) -> float:
   ```

3. **Update `compute_for_user()` and `compute_for_connection()`** to pass all 5 signals and store both new breakdown columns.

4. **Bump `AFFINITY_VERSION` to 2.**

5. **Update all unit tests** that call `_compute_affinity()` — add new arguments, update expected scores for V2 weights.

6. **Update integration tests** — check all 7 signal/metadata columns: `affinity_source_count`, `affinity_recency`, `affinity_career_overlap`, `affinity_external_contact`, `affinity_embedding_similarity`, `affinity_computed_at`, `affinity_version=2`.

7. **Update affinity scoring spec** (`linkedout_affinity_scoring.collab.md`) — delegate to `/taskos-update-spec`:
   - Promote V2 planned behaviors to main Behaviors section
   - Update formula with actual weight values
   - Correct embedding dimension from 768 to 1536
   - Bump spec version to 2

8. **Update data model spec** (`linkedout_data_model.collab.md`) — delegate to `/taskos-update-spec`:
   - Fix stale V1 formula comment (currently `0.3/0.3/0.2/0.2`) to reflect V2 weights

9. **Run `precommit-tests`** to verify nothing is broken.

10. **Run `rcv2 db compute-affinity`** against dev database. Compare V2 distribution against V1 — career overlap should dominate, small-company connections rank higher.

## Completion Criteria

- [ ] `AFFINITY_VERSION == 2`
- [ ] V2 weights defined as module constants summing to 1.0
- [ ] `_compute_affinity()` accepts all 5 signal values
- [ ] Unit test: `_compute_affinity(1.0, 1.0, 1.0, 1.0, 1.0)` returns 100.0
- [ ] Unit test: known-value test with specific inputs produces expected score
- [ ] Integration test: `compute_for_user` populates all signal columns including two new ones
- [ ] `rcv2 db compute-affinity` runs successfully with `affinity_version = 2`
- [ ] All existing tests updated for V2 weights/signatures and pass
- [ ] `precommit-tests` pass
- [ ] Affinity scoring spec updated to V2
- [ ] Data model spec formula corrected

## Verification

```bash
pytest tests/unit/intelligence/test_affinity_scorer.py -v
pytest tests/linkedout/intelligence/test_affinity_integration.py -v
precommit-tests
rcv2 db compute-affinity
psql $DATABASE_URL -c "SELECT affinity_version, COUNT(*) FROM connection GROUP BY affinity_version"
# Should show all connections at version 2
```

## Design Notes

- **Weight tuning:** These are initial values based on spec guidance. Easy to adjust (module constants). Eyeball session on top-50 after first V2 run.
- **V2 degradation:** With no contact_source rows and no embeddings, V2 degrades to `source_count * 0.10 + recency * 0.10 = max 20 points`. V1 max with same data was 75 points. Intentional — V2 rewards richer data.
- **Backward compatibility:** V1 scores overwritten. `affinity_version` column distinguishes. No downstream consumer depends on absolute scores; Dunbar tiers are rank-based.
- **Spec updates:** Two specs need updating. Both delegated to `/taskos-update-spec`. Review output for accuracy.

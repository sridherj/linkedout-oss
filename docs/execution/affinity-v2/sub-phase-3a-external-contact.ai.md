# Sub-Phase 3a: External Contact Signal

**Goal:** linkedin-ai-production
**Phase:** 3 — Affinity V2 Enhancements
**Depends on:** SP-1 (Schema Migration)
**Estimated effort:** 1 session (~2-3h)
**Source plan section:** Sub-phase 3a

---

## Objective

Connections confirmed through external contact sources (Google Contacts, phone contacts) receive a warmth bonus stored in `affinity_external_contact`. Phone contacts score 1.0, email-only 0.7, no external sources 0.0. Multiple sources don't stack — highest tier wins. When `contact_source` has 0 rows (current state), all connections get 0.0.

## Context

The old `enrich_affinity_gmail.py` used RapidFuzz name matching to link Gmail contacts to profiles. In the new schema, `contact_source.connection_id` already resolves this linkage via the import pipeline's dedup system. The scorer just reads the resolved links — no fuzzy matching needed.

**Note:** `contact_source` currently has 0 rows in production. This signal produces 0.0 for all connections until a Google Contacts CSV import is done. This is expected and forward-looking.

## Tasks

1. **Define `_compute_external_contact_score()` pure function** in `affinity_scorer.py`:
   - Input: list of contact source records for a connection (`[{source_type, phone, email}]`)
   - Define module constant `EXTERNAL_SOURCE_TYPES = {'google_contacts_job', 'gmail_email_only', 'contacts_phone'}`
   - Filter to external source types only (`linkedin_csv` excluded — it's base network data)
   - If no external sources match: return 0.0
   - If any source has phone: return 1.0
   - If any source has email (but no phone): return 0.7

2. **Add batch query `_batch_fetch_external_contacts()`** to `AffinityScorer`:
   ```sql
   SELECT cs.connection_id, cs.source_type, cs.phone, cs.email
   FROM contact_source cs
   WHERE cs.connection_id = ANY(:connection_ids)
     AND cs.source_type IN ('google_contacts_job', 'gmail_email_only', 'contacts_phone')
     AND cs.dedup_status = 'matched'
   ```
   Returns `dict[str, list[dict]]` keyed by connection_id.

3. **Wire into `compute_for_user()` and `compute_for_connection()`** — call `_compute_external_contact_score()` for each connection, store result in `conn.affinity_external_contact`.

4. **Unit tests** for the pure function:
   - `_compute_external_contact_score([])` returns 0.0
   - Connection with one email-only contact_source returns 0.7
   - Connection with one phone contact_source returns 1.0
   - Connection with both email and phone returns 1.0 (phone dominates)
   - Source types other than `EXTERNAL_SOURCE_TYPES` (e.g., `linkedin_csv`) contribute 0.0

5. **Integration test:**
   - With empty `contact_source` table, all connections get `affinity_external_contact = 0.0`
   - With a contact_source row linked to a connection, verify signal becomes nonzero

## Completion Criteria

- [ ] `_compute_external_contact_score()` pure function implemented
- [ ] `EXTERNAL_SOURCE_TYPES` constant defined
- [ ] `_batch_fetch_external_contacts()` batch query added
- [ ] Wired into `compute_for_user()` and `compute_for_connection()`
- [ ] `affinity_external_contact` column populated after scoring
- [ ] All unit tests pass
- [ ] Integration test passes with empty and non-empty contact_source

## Verification

```bash
pytest tests/unit/intelligence/test_affinity_scorer.py -v -k "external_contact"
pytest tests/linkedout/intelligence/test_affinity_integration.py -v -k "external_contact"
```

## Design Notes

- **Phone=1.0, email=0.7:** Design choice not explicitly in spec. Documented as constants. Cap at highest tier — no stacking.
- **`dedup_status = 'matched'` filter:** Ensures only resolved links are used. `contact_source.connection_id` is nullable (pending dedup).
- **`EXTERNAL_SOURCE_TYPES`:** Extensible set. Adding new source types is a one-line change.
- **Security:** All query parameters are parameterized. No user input in queries.
- **Separation of concerns:** Fuzzy matching is the import pipeline's job. Scorer just reads resolved `connection_id` links.

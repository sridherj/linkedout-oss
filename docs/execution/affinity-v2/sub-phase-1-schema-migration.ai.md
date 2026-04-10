# Sub-Phase 1: Schema Migration — New Signal Columns

**Goal:** linkedin-ai-production
**Phase:** 3 — Affinity V2 Enhancements
**Depends on:** Nothing (first sub-phase)
**Estimated effort:** 0.5 session (~1h)
**Source plan section:** Sub-phase 1

---

## Objective

Add two new float columns (`affinity_external_contact`, `affinity_embedding_similarity`) to the `connection` table and a `source_label` VARCHAR(50) column to the `contact_source` table. Generate and run an Alembic migration. Existing V1 scores remain untouched.

## Context

The `connection` table already has V1 signal columns (`affinity_source_count`, `affinity_recency`, `affinity_career_overlap`, `affinity_mutual_connections`). The two new columns follow the same `affinity_{signal_name}` naming convention. The `contact_source` table needs `source_label` to distinguish import origins for the external contact signal (SP-3a).

## Tasks

1. **Add columns to `ConnectionEntity`** in `src/linkedout/connection/entities/connection_entity.py`:
   ```python
   affinity_external_contact: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='External contact warmth signal')
   affinity_embedding_similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0, comment='Embedding similarity signal')
   ```
   Place after `affinity_mutual_connections` to keep signal columns grouped.

2. **Add `source_label` to `ContactSourceEntity`** (or `contact_source` table):
   ```python
   source_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Import origin: google_personal, google_work, icloud, office365')
   ```

3. **Generate Alembic migration:**
   ```bash
   alembic revision --autogenerate -m "add_affinity_v2_signal_columns_and_contact_source_label"
   ```
   Review generated SQL — should be two `ADD COLUMN ... DEFAULT 0` on `connection` plus one `ADD COLUMN` on `contact_source`. No data migration needed.

4. **Run migration and verify:**
   ```bash
   alembic upgrade head
   psql $DATABASE_URL -c "\d connection"  # verify new columns with default 0.0
   ```

5. **Run repository wiring tests** to confirm entity works with SQLite (unit) and PostgreSQL (integration):
   ```bash
   pytest tests/linkedout/connection/repositories/test_connection_repository.py -v
   ```

6. **Update data model spec** — delegate to `/taskos-update-spec`: add `affinity_external_contact FLOAT NOT NULL DEFAULT 0` and `affinity_embedding_similarity FLOAT NOT NULL DEFAULT 0` to the connection table definition in `linkedout_data_model.collab.md`.

## Completion Criteria

- [ ] `alembic upgrade head` runs without error
- [ ] `psql $DATABASE_URL -c "\d connection"` shows both new columns with default 0.0
- [ ] `psql $DATABASE_URL -c "\d contact_source"` shows `source_label` column
- [ ] `pytest tests/linkedout/connection/repositories/test_connection_repository.py -v` passes
- [ ] Existing `affinity_score` values unchanged after migration
- [ ] Data model spec updated with new columns

## Verification

```bash
alembic upgrade head
psql $DATABASE_URL -c "\d connection" | grep affinity_
psql $DATABASE_URL -c "SELECT COUNT(*) FROM connection WHERE affinity_external_contact != 0 OR affinity_embedding_similarity != 0"
# Should be 0 — all defaults
pytest tests/linkedout/connection/repositories/test_connection_repository.py -v
```

## Design Notes

- `ADD COLUMN ... DEFAULT 0` is metadata-only in PostgreSQL 11+ (no table rewrite). Safe for 24K+ rows.
- `source_label` is nullable for backward compat with bulk imports that don't specify origin.
- Known `source_label` values: `google_personal`, `google_work`, `icloud`, `office365`.
- The existing `affinity_mutual_connections` column (placeholder at 0.0) stays — deferred per spec.

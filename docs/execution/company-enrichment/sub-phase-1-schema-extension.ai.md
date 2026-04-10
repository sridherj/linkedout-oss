# Sub-Phase 1: Schema Extension — Add Enrichment ID Columns

**Goal:** linkedin-ai-production
**Phase:** 2 — Company Enrichment
**Depends on:** Nothing (can run in parallel with SP-2)
**Estimated effort:** 1h
**Source plan section:** Sub-phase 1

---

## Objective

Add `pdl_id` (String, nullable) and `wikidata_id` (String, nullable) columns to the `company` table via Alembic migration. Update CompanyEntity and data model spec.

## Context

- **Code directory:** `./`
- 47K companies currently have 0% industry/website/HQ coverage. These ID columns enable tracking which external source enriched each company.
- `pdl_id` stores the People Data Labs company identifier; `wikidata_id` stores the Wikidata Q-number (e.g., Q95 for Google).
- These are non-breaking, nullable column additions.

## Pre-Flight Checks

Before starting, verify:
- [ ] `alembic heads` shows a single head (no divergent migrations)
- [ ] `psql $DATABASE_URL -c "\d company"` confirms `pdl_id` and `wikidata_id` do NOT already exist
- [ ] Dev database is accessible

## Files to Create/Modify

```
./
├── src/linkedout/company/entities/company_entity.py    # Add pdl_id, wikidata_id columns
├── alembic/versions/XXXX_add_pdl_id_wikidata_id.py    # Auto-generated migration
└── docs/specs/linkedout_data_model.collab.md           # Add columns to spec (via /taskos-update-spec)
```

---

## Step 1: Add Columns to CompanyEntity

**Tasks:**
1. Open `src/linkedout/company/entities/company_entity.py`
2. Add two new columns (place them near other metadata fields):
   ```python
   pdl_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment='People Data Labs company identifier')
   wikidata_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment='Wikidata Q-number identifier')
   ```
3. Ensure `Optional` and `String` are imported.

**Verify:**
```bash
python -c "from linkedout.company.entities.company_entity import CompanyEntity; print([c.name for c in CompanyEntity.__table__.columns if 'id' in c.name])"
```
Should include `pdl_id` and `wikidata_id`.

## Step 2: Generate and Review Alembic Migration

**Tasks:**
1. Generate the migration:
   ```bash
   cd . && alembic revision --autogenerate -m "add_pdl_id_wikidata_id_to_company"
   ```
2. Review the generated migration file. Confirm it ONLY adds two columns (`pdl_id` and `wikidata_id`). No other schema changes should be present.
3. If other changes snuck in (due to ORM drift), remove them from the migration — only keep the two `add_column` operations.

**Verify:**
```bash
# Check migration content
cat alembic/versions/*add_pdl_id_wikidata_id*.py
```

## Step 3: Apply Migration

**Tasks:**
1. Run the migration:
   ```bash
   alembic upgrade head
   ```
2. Confirm columns exist:
   ```bash
   psql $DATABASE_URL -c "\d company" | grep -E "pdl_id|wikidata_id"
   ```

**Verify:**
```bash
# ORM validation
rcv2 db validate-orm
```
Must pass.

## Step 4: Update Data Model Spec

**Tasks:**
1. Delegate to `/taskos-update-spec` to add `pdl_id` and `wikidata_id` to the company table definition in `docs/specs/linkedout_data_model.collab.md`:
   ```sql
   -- External enrichment identifiers
   pdl_id                    TEXT,                     -- People Data Labs company ID
   wikidata_id               TEXT,                     -- Wikidata Q-number (e.g., Q95)
   ```
2. Review the spec update output. Confirm version was bumped.

---

## Verification Checklist

- [ ] `alembic upgrade head` succeeds
- [ ] `psql $DATABASE_URL -c "\d company"` shows `pdl_id` and `wikidata_id` columns
- [ ] `from linkedout.company.entities.company_entity import CompanyEntity` — columns present
- [ ] `rcv2 db validate-orm` passes
- [ ] Data model spec updated with new columns

## Rollback

```bash
alembic downgrade -1
```
This removes the two columns. No data loss (columns are new and empty).

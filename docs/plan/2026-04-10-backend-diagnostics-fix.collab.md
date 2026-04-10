# Backend Diagnostics Fix Plan

## Context

The app has two categories of broken pages/data: missing DB tables (causing 500 crashes) and unpopulated fields (causing charts to show all-Unknown/Unassigned). This plan addresses all five issues identified.

---

## Part 1 — Code Problems (Missing Migrations)

Yes — these are fully implemented in code and simply never had a migration generated. Checking all entities registered in `migrations/env.py` against actual migration files reveals **7 tables with no migration** (not just 2):

| Table | Entity |
|-------|--------|
| `search_history` | `SearchHistoryEntity` |
| `import_job` | `ImportJobEntity` |
| `role_alias` | `RoleAliasEntity` |
| `enrichment_event` | `EnrichmentEventEntity` |
| `contact_source` | `ContactSourceEntity` |
| `company_alias` | `CompanyAliasEntity` |
| `enrichment_config` | `EnrichmentConfigEntity` |

One `alembic revision --autogenerate` run catches all of them.

**Step**: Run migration generation + apply.
```bash
alembic revision --autogenerate -m "add_missing_linkedout_tables"
alembic upgrade head
```

**Verify**: History page and Import history page no longer crash with 500.

---

## Part 2 — "None" String in full_name

### Root causes (two bugs)

**Bug A** — `src/dev_tools/load_apify_profiles.py:142`

When Apify returns `null` for `firstName` but a real value for `lastName` (or vice versa), the f-string `f'{None} Smith'` produces `"None Smith"` in the database.

```python
# Current (buggy):
first_name = profile.get('firstName', '')
last_name = profile.get('lastName', '')
full_name = f'{first_name} {last_name}'.strip() if (first_name or last_name) else None
# When firstName=null, lastName='Smith': produces "None Smith"

# Fix:
parts = [p for p in [first_name, last_name] if p]
full_name = ' '.join(parts) if parts else None
```

**Bug B** — `src/linkedout/intelligence/agents/search_agent.py:106,140`

`str(row.get("full_name", ""))` returns `str(None)` = `"None"` when the DB column is NULL (key exists with None value, so the default `""` is not used).

```python
# Current (buggy):
full_name=str(row.get("full_name", "")),

# Fix:
full_name=row.get("full_name") or "",
```
Same fix at line 140.

### Data cleanup

After fixing the code, run a SQL UPDATE to repair existing rows:
```sql
UPDATE crawled_profile
SET full_name = CASE
    WHEN first_name IS NOT NULL AND last_name IS NOT NULL THEN first_name || ' ' || last_name
    WHEN first_name IS NOT NULL THEN first_name
    WHEN last_name IS NOT NULL THEN last_name
    ELSE NULL
END
WHERE full_name LIKE '%None%';
```

Add as a CLI command `rcv2 db fix-none-names [--dry-run]` in `src/dev_tools/cli.py` that runs this SQL and reports affected row count.

---

## Part 3 — Seniority Distribution + Industry Breakdown all "Unknown"

### Root cause

`crawled_profile.seniority_level` and `function_area` are never set by the enrichment pipeline. The `role_alias` table is a lookup: `alias_title (unique) → seniority_level + function_area`.

### Fix

**Step 1**: Add `get_by_alias_title(title: str) -> Optional[RoleAliasEntity]` to `src/linkedout/role_alias/repositories/role_alias_repository.py`.

**Step 2**: In `src/linkedout/enrichment_pipeline/post_enrichment.py`, inject `RoleAliasRepository` and after setting `current_position`, do:
```python
if profile.current_position:
    alias = self._role_alias_repo.get_by_alias_title(profile.current_position)
    if alias:
        profile.seniority_level = alias.seniority_level
        profile.function_area = alias.function_area
```

**Step 3**: Add CLI command `rcv2 db backfill-seniority [--dry-run] [--limit N]` in `src/dev_tools/cli.py` + `src/dev_tools/backfill_seniority.py`.
- Iterates all `crawled_profile` rows where `seniority_level IS NULL` and `current_position IS NOT NULL`
- Looks up each `current_position` in `role_alias` via exact match (`alias_title`)
- Sets `seniority_level` and `function_area` if found
- Reports matched/total counts

**Verify**: After running `rcv2 db backfill-seniority`, the Seniority Distribution and Industry Breakdown charts show real data.

---

## Part 4 — Affinity Tiers all "Unassigned"

### Root cause

`AffinityScorer.compute_for_user(app_user_id, reference_date)` exists in `src/linkedout/intelligence/scoring/affinity_scorer.py` but is never called anywhere.

### Fix

Add CLI command `rcv2 db compute-affinity [--user-id USER_ID] [--dry-run]` in `src/dev_tools/cli.py` + `src/dev_tools/compute_affinity.py`.

Logic:
```python
from linkedout.intelligence.scoring.affinity_scorer import AffinityScorer

with session_scope() as session:
    if user_id:
        users = [session.get(AppUserEntity, user_id)]
    else:
        users = session.query(AppUserEntity).filter(AppUserEntity.is_active == True).all()

    for user in users:
        count = AffinityScorer(session).compute_for_user(user.id)
        click.echo(f"  {user.id}: updated {count} connections")
    session.commit()
```

**Verify**: After running `rcv2 db compute-affinity`, the Affinity Tiers chart shows inner_circle / active / familiar / acquaintance distribution.

**Q: When does affinity scoring run?**

Affinity is **precomputed**, not computed at query time — the scores live in the `connection` table. Right now nothing triggers it. The intended design for this tool:

1. **CLI for initial/backfill** (this plan): `rcv2 db compute-affinity` — run once after importing all connections
2. **Auto-trigger after import**: hook `compute_for_user` at the end of `load-linkedin-csv` and `load-gmail-contacts` so scores stay current after every data load
3. **FE "Refresh Scores" button** (future): expose `POST /api/affinity/recompute` endpoint — the FE calls this; no need for user to touch the CLI

For this plan we implement (1). We also add (2) to the import commands so it runs automatically going forward.

---

## Files to Modify

| File | Change |
|------|--------|
| `src/dev_tools/load_apify_profiles.py:140-142` | Fix f-string None interpolation |
| `src/linkedout/intelligence/agents/search_agent.py:106,140` | Fix `str(None)` → `or ""` |
| `src/linkedout/role_alias/repositories/role_alias_repository.py` | Add `get_by_alias_title` |
| `src/linkedout/enrichment_pipeline/post_enrichment.py` | Inject role_alias repo, set seniority/function after enrichment |
| `src/dev_tools/cli.py` | Add 3 new `db` commands |
| `src/dev_tools/backfill_seniority.py` | New file: backfill logic |
| `src/dev_tools/compute_affinity.py` | New file: affinity scoring runner |
| `src/dev_tools/fix_none_names.py` | New file: SQL cleanup logic |

## Execution Order

1. `alembic revision --autogenerate -m "add_search_history_and_import_job_tables"`
2. `alembic upgrade head`
3. `rcv2 db fix-none-names` — clean up existing bad full_name data
4. `rcv2 db backfill-seniority` — populate seniority/function for existing profiles
5. `rcv2 db compute-affinity` — compute affinity tiers for all users

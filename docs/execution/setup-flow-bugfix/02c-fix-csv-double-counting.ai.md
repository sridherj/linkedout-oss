# Sub-phase 02c: Fix CSV Import Double-Counting

## Metadata
- **Depends on:** 01-foundation-bootstrap (FK records must exist for verification)
- **Blocks:** 04-spec-updates, 05-tests
- **Estimated scope:** 1 file modified
- **Plan section:** Phase 2c (Issue 12) — HIGH PRIORITY

## Context

Read `_shared_context.md` for fixed_data imports and system record IDs.

## Task

**File:** `backend/src/linkedout/commands/import_connections.py`, `load_csv_batch()`,
lines 112-176

**Root cause chain:**
1. System records don't exist -> FK violation on `ConnectionEntity` INSERT
2. Counter for `unenriched`/`matched`/`no_url` incremented BEFORE `savepoint.commit()`
3. FK violation -> exception -> `savepoint.rollback()` undoes stub profile, but counter
   was already incremented
4. `errors` counter also incremented -> same row counted twice
5. Net: `succeeded: 15, failed: 15` for 15 rows, 0 profiles actually in DB

**Fix:** Defer counter increments and `url_index` mutation until after `savepoint.commit()`:

```python
for row in batch:
    counts['total'] += 1
    savepoint = session.begin_nested()
    try:
        # ... parsing unchanged ...

        pending_counter = None
        pending_url_entry = None  # (url, profile_id) to cache after commit

        if norm_url and norm_url in url_index:
            profile_id = url_index[norm_url]
            pending_counter = 'matched'
        elif norm_url:
            stub = create_stub_profile(first_name, last_name, norm_url, company, position, now)
            session.add(stub)
            session.flush()
            profile_id = stub.id
            pending_url_entry = (norm_url, profile_id)
            pending_counter = 'unenriched'
        else:
            stub = create_stub_profile(first_name, last_name, None, company, position, now)
            session.add(stub)
            session.flush()
            profile_id = stub.id
            pending_counter = 'no_url'

        # ... connection entity creation unchanged ...
        session.add(connection)
        savepoint.commit()

        # Commit succeeded — now safe to update counters and index
        counts[pending_counter] += 1
        if pending_url_entry:
            url_index[pending_url_entry[0]] = pending_url_entry[1]

    except Exception as e:
        savepoint.rollback()
        counts['errors'] += 1
        name = f'{row.get("First Name", "")} {row.get("Last Name", "")}'.strip()
        click.echo(f'  Error on row ({name}): {e}', err=True)
```

**Edge case (accepted):** If two rows in same batch have the same URL, the second creates
a duplicate stub (first row's `url_index` entry deferred to after commit). The
`uq_conn_app_user_profile` constraint catches duplicates. This is better than importing
0 profiles.

## Verification
Import CSV with N rows:
- `total=N`, `matched+unenriched+no_url+errors=N` (exactly N, not 2N)
- `SELECT count(*) FROM crawled_profile` matches expected inserts

## Completion Criteria
- [ ] Counter increments moved after `savepoint.commit()`
- [ ] `url_index` mutation moved after `savepoint.commit()`
- [ ] Error handler only increments `errors` counter
- [ ] No lint errors

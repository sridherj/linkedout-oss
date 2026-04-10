# Sub-phase 02d: Fix Hardcoded IDs (DRY)

## Metadata
- **Depends on:** nothing
- **Blocks:** 04-spec-updates, 05-tests
- **Estimated scope:** 2 files modified
- **Plan section:** Phase 2d (Issue 13 + DRY)

## Context

Read `_shared_context.md` for fixed_data imports and system record IDs.

## Task

### File 1: `backend/src/linkedout/setup/enrichment.py`

Line 106 already imports `SYSTEM_USER_ID` from `dev_tools.db.fixed_data`. Add
`SYSTEM_TENANT` and `SYSTEM_BU` to that import.

Lines 178-179 change from:
```python
tenant_id="default",
bu_id="default",
```
To:
```python
tenant_id=SYSTEM_TENANT['id'],
bu_id=SYSTEM_BU['id'],
```

### File 2: `backend/src/linkedout/commands/import_connections.py`

Lines 34-36 hardcode the same IDs:
```python
APP_USER_ID = 'usr_sys_001'
TENANT_ID = 'tenant_sys_001'
BU_ID = 'bu_sys_001'
```

Replace with imports from `fixed_data`:
```python
from dev_tools.db.fixed_data import SYSTEM_USER_ID, SYSTEM_TENANT, SYSTEM_BU

APP_USER_ID = SYSTEM_USER_ID
TENANT_ID = SYSTEM_TENANT['id']
BU_ID = SYSTEM_BU['id']
```

## Verification
```sql
SELECT tenant_id, bu_id FROM enrichment_event;
```
Shows `tenant_sys_001`, `bu_sys_001` (not `default`).

CSV import still uses correct IDs.

## Completion Criteria
- [ ] `enrichment.py` uses `SYSTEM_TENANT['id']` and `SYSTEM_BU['id']`
- [ ] `import_connections.py` imports from `fixed_data` instead of hardcoding
- [ ] No lint errors

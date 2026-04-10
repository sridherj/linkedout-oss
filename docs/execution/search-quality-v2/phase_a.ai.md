# Phase A: Expose Funding Tables to Schema Context

**Effort:** 15 minutes
**Dependencies:** None (can start immediately)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Make `funding_round` and `startup_tracking` tables visible to the LLM so it can query funding stage, investors, total raised, etc. Currently these tables exist (198 and 182 rows respectively) but the search agent can't see them.

## What to Do

### 1. Add entities to schema context

**File:** `./src/linkedout/intelligence/schema_context.py`

Add imports:
```python
from linkedout.funding.entities.funding_round_entity import FundingRoundEntity
from linkedout.funding.entities.startup_tracking_entity import StartupTrackingEntity
```

Add to `_ENTITIES` list (around line 17):
```python
FundingRoundEntity, StartupTrackingEntity,  # NEW — funding data
```

### 2. Add tables to SQL tool whitelist

**File:** `./src/linkedout/intelligence/tools/sql_tool.py`

Add to `_AVAILABLE_TABLES` (around line 15):
```python
'funding_round', 'startup_tracking',
```

### 3. Add business rules for funding tables

**File:** `./src/linkedout/intelligence/schema_context.py`

Add to `_BUSINESS_RULES`:
```
- `funding_round` links to `company` via `company_id`. Contains round_type, amount_usd, lead_investors (text array), all_investors (text). NOT user-scoped (no RLS) — public company data.
- `startup_tracking` links to `company` via `company_id` (1:1). Contains funding_stage, total_raised_usd, vertical, watching flag. NOT user-scoped.
```

## Verification

```bash
# Unit tests pass (no regressions)
pytest tests/unit/intelligence/ -v

# Integration tests pass (including new funding table test)
pytest tests/integration/linkedout/intelligence/ -v

# Smoke test: verify schema context includes new tables
python -c "
from linkedout.intelligence.schema_context import get_schema_context
ctx = get_schema_context()
assert 'funding_round' in ctx, 'funding_round not in schema context'
assert 'startup_tracking' in ctx, 'startup_tracking not in schema context'
print('OK: funding tables in schema context')
"
```

### Integration test to add

**File:** `tests/integration/linkedout/intelligence/test_search_integration.py`

Add a test verifying `funding_round` and `startup_tracking` are queryable via `execute_sql` with RLS session:

```python
def test_funding_tables_queryable_via_rls_session(self, search_db_session):
    """Verify funding tables are accessible through execute_sql with RLS session."""
    # Query funding_round
    result = execute_sql("SELECT COUNT(*) FROM funding_round", session=search_db_session)
    assert result is not None
    
    # Query startup_tracking
    result = execute_sql("SELECT COUNT(*) FROM startup_tracking", session=search_db_session)
    assert result is not None
    
    # Join funding data with company (the key relationship)
    result = execute_sql(
        "SELECT c.canonical_name, fr.round_type, fr.amount_usd "
        "FROM funding_round fr JOIN company c ON c.id = fr.company_id LIMIT 5",
        session=search_db_session
    )
    assert result is not None
```

## Expected Impact

+1-2 points on queries: sj_03 (probably hiring), rec_03 (eng leadership at Series B-C), fnd_06 (early employees at funded startups), and any query involving funding stage/investors/startup classification.

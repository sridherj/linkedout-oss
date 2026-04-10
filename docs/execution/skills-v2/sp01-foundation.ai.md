# SP01: Fix the Foundation — Diagnostics + Readiness Alignment

## Context

Read `_shared_context.md` first for entity names, system record IDs, and key constraints.

Every other skill depends on being able to answer "is the system healthy?" accurately. Today,
`diagnostics.py` and `readiness.py` are two disconnected systems. Readiness shells out to
diagnostics via subprocess (and references a `--ping` flag that doesn't exist). This sub-phase
fixes the foundation so Phases 3-6 can build on correct data.

## Scope

Plan Phases 1a through 1e (all tightly coupled — same modules, same test files).

## Tasks

### 1a. Extend `get_db_stats()` with new fields

**File:** `backend/src/shared/utilities/health_checks.py`

`get_db_stats()` currently returns 7 fields (profiles_total, profiles_with_embeddings,
profiles_without_embeddings, companies_total, connections_total, last_enrichment, schema_version).

Add these new fields to the return dict:

```python
# New — enrichment
'profiles_enriched': 0,          # CrawledProfileEntity.has_enriched_data = True
'profiles_unenriched': 0,        # CrawledProfileEntity.has_enriched_data = False
'enrichment_events_total': 0,    # COUNT(*) from enrichment_event

# New — affinity
'connections_with_affinity': 0,   # ConnectionEntity.affinity_score IS NOT NULL
'connections_without_affinity': 0,

# New — owner profile
'owner_profile_exists': False,    # CrawledProfileEntity WHERE data_source = 'setup'

# New — system records
'system_tenant_exists': False,    # tenant WHERE id = 'tenant_sys_001'
'system_bu_exists': False,        # bu WHERE id = 'bu_sys_001'
'system_user_exists': False,      # app_user WHERE id = 'usr_sys_001'

# New — seed data
'seed_companies_loaded': 0,       # total company count (CompanyEntity has no source column)
'funding_rounds_total': 0,        # COUNT(*) from funding_round
```

**Implementation notes:**
- Follow the existing lazy-import pattern (imports inside try/except in function body)
- Import `ConnectionEntity` (check existing imports), `TenantEntity`, `BuEntity`, `AppUserEntity`
  from `organization/entities/`, `FundingRoundEntity` from `linkedout.funding.entities.funding_round_entity`
- Each new field is a single query within the existing session context
- `CompanyEntity` has NO `source` column — use total count for `seed_companies_loaded`

Also add an optional `session` parameter to `check_db_connection()` (it currently creates its own
via `cli_db_manager()`). If a session is passed, use it; otherwise create one as before.

### 1b. Add `compute_issues()` function

**File:** `backend/src/shared/utilities/health_checks.py` (add new function)

Create a `compute_issues()` function that turns raw stats + health checks into structured issues:

```python
def compute_issues(db_stats: dict, health_checks: list[dict]) -> list[dict]:
    """Derive actionable issues from raw diagnostics data."""
    issues = []

    # System records
    if not db_stats.get('system_tenant_exists'):
        issues.append({
            'severity': 'CRITICAL', 'category': 'bootstrap',
            'message': 'System tenant record missing — CSV import and enrichment will fail',
            'action': 'linkedout setup --demo  # or --full',
        })

    # Owner profile
    if not db_stats.get('owner_profile_exists') and db_stats.get('profiles_total', 0) > 0:
        issues.append({
            'severity': 'WARNING', 'category': 'setup',
            'message': 'Owner profile not configured — affinity scoring needs your profile as baseline',
            'action': 'Run /linkedout-setup and provide your LinkedIn URL',
        })

    # Embeddings
    without_emb = db_stats.get('profiles_without_embeddings', 0)
    if without_emb > 0:
        issues.append({
            'severity': 'WARNING', 'category': 'embeddings',
            'message': f'{without_emb:,} profiles without embeddings — semantic search won\'t find them',
            'action': 'linkedout embed',
        })

    # Enrichment
    unenriched = db_stats.get('profiles_unenriched', 0)
    if unenriched > 0:
        issues.append({
            'severity': 'INFO', 'category': 'enrichment',
            'message': f'{unenriched:,} profiles not enriched — only name/company/title available',
            'action': 'linkedout enrich  # requires Apify key',
        })

    # Affinity
    without_affinity = db_stats.get('connections_without_affinity', 0)
    if without_affinity > 0:
        issues.append({
            'severity': 'INFO', 'category': 'affinity',
            'message': f'{without_affinity:,} connections without affinity scores',
            'action': 'linkedout compute-affinity',
        })

    # Health check failures
    for check in health_checks:
        if check['status'] == 'fail':
            issues.append({
                'severity': 'CRITICAL', 'category': check['check'],
                'message': check.get('detail', f'{check["check"]} failed'),
                'action': 'linkedout diagnostics --repair',
            })

    return issues
```

### 1c. Wire issues + health badge into diagnostics report

**File:** `backend/src/linkedout/commands/diagnostics.py`

In `_build_report()` (around line 128-135), import `compute_issues` from `health_checks` and add
`issues` and `health_status` to the returned dict:

```python
from shared.utilities.health_checks import compute_issues

issues = compute_issues(db_stats, health_checks)

# Count by severity
counts = {'CRITICAL': 0, 'WARNING': 0, 'INFO': 0}
for issue in issues:
    counts[issue['severity']] = counts.get(issue['severity'], 0) + 1

# Badge logic
if counts['CRITICAL'] > 0:
    badge = 'ACTION_REQUIRED'
elif counts['WARNING'] > 0:
    badge = 'NEEDS_ATTENTION'
else:
    badge = 'HEALTHY'

# Add to report dict
report['health_status'] = {
    'badge': badge,
    'critical': counts['CRITICAL'],
    'warning': counts['WARNING'],
    'info': counts['INFO'],
}
report['issues'] = issues
```

### 1d. Replace readiness subprocess calls with direct imports

**File:** `backend/src/linkedout/setup/readiness.py`

Replace `_query_db_counts()` (line ~387) which shells out to `linkedout diagnostics --json` via
subprocess with direct Python call to `get_db_stats()`:

```python
def _query_db_counts(log) -> dict:
    counts = {
        'profiles_loaded': 0, 'profiles_with_embeddings': 0,
        'profiles_without_embeddings': 0, 'companies_loaded': 0,
        'companies_missing_aliases': 0, 'role_aliases_loaded': 0,
        'connections_total': 0, 'connections_with_affinity': 0,
        'connections_without_affinity': 0, 'connections_company_matched': 0,
        'seed_tables_populated': 0,
    }
    try:
        from shared.utilities.health_checks import get_db_stats
        stats = get_db_stats()
        counts['profiles_loaded'] = stats.get('profiles_total', 0)
        counts['profiles_with_embeddings'] = stats.get('profiles_with_embeddings', 0)
        counts['profiles_without_embeddings'] = stats.get('profiles_without_embeddings', 0)
        counts['companies_loaded'] = stats.get('companies_total', 0)
        counts['connections_total'] = stats.get('connections_total', 0)
        counts['connections_with_affinity'] = stats.get('connections_with_affinity', 0)
        counts['connections_without_affinity'] = stats.get('connections_without_affinity', 0)
    except Exception as exc:
        log.warning("Failed to collect DB stats: {}", exc)
    return counts
```

Replace `_check_db_connected()` (line ~477) which shells out to `linkedout diagnostics --ping`
(a flag that doesn't exist) with a direct call, passing the existing session:

```python
def _check_db_connected(session=None) -> bool:
    try:
        from shared.utilities.health_checks import check_db_connection
        return check_db_connection(session=session).status == 'pass'
    except Exception:
        return False
```

### 1e. Fix diagnostics `--repair` CLI entry point

**File:** `backend/src/linkedout/commands/diagnostics.py`, line ~223

Change:
```python
subprocess.run([sys.executable, '-m', 'linkedout.cli', 'embed'], check=False)
```
To:
```python
subprocess.run(['linkedout', 'embed'], check=False)
```

### 1f. Report filenames (no code change)

CLI already writes `diagnostic-*.json`. The `/linkedout-setup-report` skill will be updated in
SP03 to read `diagnostic-*.json` (not `setup-report-*.json`). No backend code change needed.

## Tests

### Update existing: `backend/tests/unit/shared/utilities/test_health_checks.py`
- Extend `TestGetDbStats` to verify new fields present with correct defaults
- `test_get_db_stats_enrichment_fields` — mock profiles with/without `has_enriched_data`
- `test_get_db_stats_affinity_fields` — mock connections with/without `affinity_score`
- `test_get_db_stats_system_records` — mock tenant/bu/user existence
- `test_get_db_stats_backward_compatible` — original 7 fields still present

### New file: `backend/tests/unit/linkedout/commands/test_diagnostics.py`
- `test_compute_issues_empty_on_healthy_system` — all good -> empty issues
- `test_compute_issues_critical_on_missing_tenant` — `system_tenant_exists: False` -> CRITICAL
- `test_compute_issues_warning_on_missing_embeddings` — WARNING with count
- `test_compute_issues_info_on_unenriched` — INFO issue
- `test_compute_issues_critical_on_health_check_fail` — health check fail -> CRITICAL
- `test_health_status_healthy_on_clean_system` — badge HEALTHY, all counts 0
- `test_health_status_action_required_on_critical` — badge ACTION_REQUIRED
- `test_health_status_needs_attention_on_warning` — badge NEEDS_ATTENTION
- `test_build_report_includes_issues_and_status` — `_build_report()` has both keys

### Update existing: `backend/tests/linkedout/setup/test_readiness.py`
- Change mocks from `subprocess.run` to `shared.utilities.health_checks.get_db_stats`
- `test_query_db_counts_maps_from_health_checks` — verify field mapping
- `test_query_db_counts_handles_import_error` — graceful fallback
- `test_check_db_connected_uses_health_check` — direct call, no subprocess

## Verification

```bash
# All new DB stats fields present
linkedout diagnostics --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['database'].keys())"

# Health badge and issues
linkedout diagnostics --json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['health_status']['badge'], len(d['issues']))"

# Readiness uses direct calls (no subprocess)
linkedout setup  # readiness step shows DB counts, not zeros

# Repair uses correct entry point
linkedout diagnostics --repair  # should run `linkedout embed`, not sys.executable

# Tests pass
cd backend && python -m pytest tests/unit/shared/utilities/test_health_checks.py tests/unit/linkedout/commands/test_diagnostics.py tests/linkedout/setup/test_readiness.py -v
```

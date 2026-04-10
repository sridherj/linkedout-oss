# Fix Setup Flow Issues

## Context

Three integration test runs (2 automated, 1 interactive) exposed 14 issues in the
LinkedOut setup flow. 2 are already fixed, 12 remain open. The issues file is at
`/tmp/issues.md` for reference.

**The critical cascade:** System tenant/BU/user records are never bootstrapped after
migrations. This causes FK violations on `ConnectionEntity` INSERT (which references
`app_user.id`, `tenant.id`, `bu.id`). Every CSV import row errors, savepoint rollback
undoes the stub profiles, and 0 profiles end up in the DB. Enrichment, embeddings, and
affinity then have nothing to work with.

The issues cluster into 4 groups:
1. Missing DB bootstrap (root cause of the cascade)
2. Code bugs in setup modules
3. Skill instructions that don't work in non-TTY Claude Code
4. Spec doesn't document bootstrap or conventions

---

## Phase 1: Foundation — Bootstrap System Records + Setup Script

**Why first:** Issue 14 (missing bootstrap) is the FK root cause. Every downstream fix
depends on these records existing. Issue 3 blocks the `./setup --auto` entry point.

### 1a. Bootstrap system records into `setup_database()` (Issue 14)

Fold bootstrap into the existing database step — after migrations + schema verification,
before `agent-context.env` generation. This avoids renumbering all 15 hardcoded step
strings across 10 files.

**File:** `backend/src/linkedout/setup/database.py`

Add `bootstrap_system_records(database_url)` that:
- Imports `SYSTEM_TENANT`, `SYSTEM_BU`, `SYSTEM_APP_USER` from `dev_tools.db.fixed_data`
- Connects via SQLAlchemy `create_engine(database_url)`
- Only runs if `verify_schema()` passed (guard: `if not missing:`) — if tables don't
  exist, bootstrap would fail with "relation does not exist", producing a confusing
  double-error
- Executes 3 idempotent INSERTs (order matters — FK dependencies):

```sql
-- 1. Tenant first (no FK deps)
INSERT INTO tenant (id, name, created_at, updated_at)
VALUES ('tenant_sys_001', 'System Tenant', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 2. BU second (FK to tenant)
INSERT INTO bu (id, tenant_id, name, created_at, updated_at)
VALUES ('bu_sys_001', 'tenant_sys_001', 'System BU', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

-- 3. App user third (no FK to tenant/BU directly)
INSERT INTO app_user (id, email, name, auth_provider_id, created_at, updated_at)
VALUES ('usr_sys_001', 'system@linkedout.local', 'System Admin', 'system|admin001', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;
```

**Key details:**
- Table is `bu`, NOT `business_unit` (entity class is `BuEntity`, `__tablename__ = 'bu'`)
- `created_at`/`updated_at` are mandatory — `BaseEntity` uses Python-side `default=`, NOT
  `server_default`, so raw SQL must provide them explicitly
- `is_active` and `version` have `server_default` ('true' / '1') — safe to omit
- `app_user_tenant_role` is NOT bootstrapped — CSV import and enrichment don't reference it
  via FK. Can add later if RLS needs it.
- Values come from `fixed_data.py` constants, not hardcoded — use dict field access

Call site in `setup_database()`: insert between the "Step 5: Verify schema" block
(~line 356) and the "Step 6: Generate agent-context.env" block (~line 364). Guard behind
`if not missing:`. Verify `total_steps` current value before incrementing (plan assumes 5,
confirm by reading the variable definition at the top of `setup_database()`).

**Verify:** `SELECT id FROM tenant WHERE id = 'tenant_sys_001'` returns 1 row. Run
`linkedout setup` twice — no errors, no duplicate rows.

### 1b. Fix `./setup --auto` (Issue 3)

**File:** `setup` (repo root), line 285

The one-shot eval chain appends `source $HOME/.local/bin/env 2>/dev/null` at the end.
After `curl | sh` installs uv, the env file may not exist yet. The `source` fails, the
entire `eval` exits non-zero, and the script reports "Auto-install failed" even though
everything installed fine.

**Fix:** `|| true` on the source line:
```bash
one_shot="${one_shot}source \$HOME/.local/bin/env 2>/dev/null || true"
```

**Verify:** `./setup --auto` exits 0 when deps install but `~/.local/bin/env` is missing.

---

## Phase 2: Code Bugs (Issues 10, 11, 12, 13)

All independent. Issue 12 verification requires Phase 1 (FK records must exist).

### 2a. Fix raw SQL missing timestamps (Issue 10)

**File:** `backend/src/linkedout/setup/user_profile.py`, lines 138-141

The INSERT into `crawled_profile` omits `created_at` and `updated_at`, which are NOT NULL
with Python-side-only defaults (no `server_default`). Hits `NotNullViolation`.

**Fix:** Add both columns:
```sql
INSERT INTO crawled_profile
  (id, linkedin_url, public_identifier, data_source, created_at, updated_at)
VALUES (:id, :url, :pid, 'setup', NOW(), NOW())
```

**Verify:** After user_profile step, `SELECT created_at, updated_at FROM crawled_profile
WHERE data_source='setup'` both return non-null timestamps.

### 2b. Replace `sys.executable -m linkedout.commands` with `linkedout` CLI (Issue 11)

11 occurrences across 7 files. The `linkedout` entry point is installed by
`pip install -e backend/` and respects the active venv.

| File | Lines | Remove `import sys`? |
|------|-------|---------------------|
| `setup/csv_import.py` | 189 | Yes — only usage |
| `setup/contacts_import.py` | 156 | Yes — only usage |
| `setup/auto_repair.py` | 160 | Yes — only usage |
| `setup/readiness.py` | 409, 481 | Yes — only usage |
| `setup/seed_data.py` | 67, 118 | Yes — only usage |
| `setup/affinity.py` | 47, 86 | Yes — only usage |
| `setup/embeddings.py` | 59, 171 | Yes — only usage |

Each `[sys.executable, "-m", "linkedout.commands", ...]` becomes `["linkedout", ...]`.

Note: `skill_install.py` uses `sys.executable` to run a Python script (different pattern),
and `logging_integration.py` reads `sys.executable` for diagnostics — both are correct
and should NOT be changed.

**After making changes:** Run existing tests `test_csv_import.py` and
`test_contacts_import.py` to verify no assertions break. Current tests use `in` checks
on the command list, which should tolerate the change, but verify explicitly.

**Verify:** `grep -r "sys.executable" backend/src/linkedout/setup/` returns only
`skill_install.py` and `logging_integration.py`.

### 2c. Fix CSV import double-counting (Issue 12) — HIGH PRIORITY

**File:** `backend/src/linkedout/commands/import_connections.py`, `load_csv_batch()`,
lines 112-176

**Root cause chain:**
1. System records don't exist (Issue 14) -> FK violation on `ConnectionEntity` INSERT
2. Counter for `unenriched`/`matched`/`no_url` incremented at lines 132/139/145 BEFORE
   `savepoint.commit()` at line 168
3. FK violation at line 167 -> exception -> `savepoint.rollback()` at line 171 undoes
   the stub profile, but counter was already incremented
4. `errors` counter also incremented at line 172 -> same row counted twice
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

**Edge case:** If two rows in the same batch have the same URL, the second one won't find
it in `url_index` (because the first row's entry is deferred to after commit). This means
the second row creates a duplicate stub. This is acceptable — the `uq_conn_app_user_profile`
constraint on `connection` will catch the duplicate, and it's better than the current
behavior of importing 0 profiles.

**Verify:** Import CSV with N rows. `total=N`, `matched+unenriched+no_url+errors=N`
(exactly N, not 2N). `SELECT count(*) FROM crawled_profile` matches expected inserts.

### 2d. Fix hardcoded IDs in enrichment AND import_connections (Issue 13 + DRY)

**File 1:** `backend/src/linkedout/setup/enrichment.py`

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

**File 2:** `backend/src/linkedout/commands/import_connections.py`

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

Same data, single source of truth.

**Verify:** `SELECT tenant_id, bu_id FROM enrichment_event` shows `tenant_sys_001`,
`bu_sys_001` (not `default`). CSV import still uses correct IDs.

---

## Phase 3: Skill Rewrite + Non-TTY Handling (Issues 4, 5, 6, 7, 8, 9)

All six issues stem from one design flaw: the skill sources `agent-context.env` (which
doesn't exist yet) and fires `linkedout setup --full` without pre-configuring inputs.
The orchestrator's interactive prompts (`input()`, `getpass()`) then block in Claude Code's
non-TTY Bash tool, causing EOFError.

### Critical finding: pre-writing config does NOT eliminate all `input()` calls

Even when `secrets.yaml` exists with API keys, `collect_api_keys()` still calls `input()`
to ask "Replace it? [y/N]" (lines 331, 353, 381). Same pattern in `user_profile.py`,
`csv_import.py`, `seed_data.py`, `contacts_import.py`, `embeddings.py`, `enrichment.py`,
`skill_install.py`, and `auto_repair.py`. Pre-writing config changes the prompts but
doesn't eliminate them.

`demo_offer.py` already handles this correctly with `try/except (EOFError, KeyboardInterrupt)`.

### 3a. Add EOFError handling to all `input()` calls in setup modules

Every `input()` call in setup modules should follow the `demo_offer.py` pattern:
```python
try:
    choice = input("Replace it? [y/N] ").strip().lower()
except (EOFError, KeyboardInterrupt):
    choice = ""  # default to "no" / keep existing
```

The default behavior on EOFError should be the safe/conservative choice:
- "Replace key?" -> No (keep existing)
- "Change provider?" -> No (keep existing)
- "Install skills?" -> Yes (skills are needed)
- "Enrich profiles?" -> Yes (if key exists)
- "Enter path:" -> skip (can't provide a path non-interactively)

**Files to update (every `input()` / `getpass()` call):**
- `api_keys.py` — 6 calls (lines 98, 113, 125, 171, 331, 353, 381)
- `user_profile.py` — 3 calls (lines 56, 58, 175)
- `csv_import.py` — 4 calls (lines 111, 122, 129, 134)
- `contacts_import.py` — 3 calls (lines 68, 79, 221)
- `seed_data.py` — 1 call (line 220)
- `embeddings.py` — 1 call (line 265)
- `enrichment.py` — 1 call (line 278)
- `skill_install.py` — 1 call (line 339)
- `auto_repair.py` — 1 call (line 134)

### 3b. Rewrite the skill template

**Files:**
- `skills/linkedout-setup/SKILL.md.tmpl` (source template)
- `skills/claude-code/linkedout-setup/SKILL.md` (rendered output — regenerate after)

**New flow:**

**Step 1: Ask demo vs full** (same as current — wait for answer before proceeding)

**Step 2: Demo path** — no config collection needed:
```bash
cd $(git rev-parse --show-toplevel)/backend && \
  uv venv .venv && source .venv/bin/activate && \
  uv pip install -r requirements.txt && \
  linkedout setup --demo
```
- NO `source agent-context.env` before setup — it doesn't exist yet (Issue 8)
- Demo path needs no API keys (local embeddings, pre-computed affinity)

**Step 3: Full setup path — collect ALL inputs FIRST** (Issues 4, 5, 6, 9)

Before running any setup commands, conversationally collect:
1. **Embedding provider** — openai (recommended, ~$0.01/1K profiles) or local (free, 275 MB)
2. **OpenAI API key** — if they chose openai
3. **Apify API key** — optional, for profile enrichment (~$4/1K profiles, $5/month free)
4. **LinkedIn profile URL** — their own profile (anchor for affinity scoring)
5. **Connections.csv path** — or skip if they haven't exported yet

Then write config files:
```bash
mkdir -p ~/linkedout-data/config

cat > ~/linkedout-data/config/secrets.yaml << 'EOF'
openai_api_key: "sk-..."
apify_api_key: "apify_api_..."  # omit line if not provided
EOF
chmod 600 ~/linkedout-data/config/secrets.yaml
```

Then run setup:
```bash
cd $(git rev-parse --show-toplevel)/backend && \
  source .venv/bin/activate && \
  linkedout setup --full
```

With 3a's EOFError handling in place, the orchestrator will find existing config and
default to keeping it (no interactive prompt needed). Steps that require user-specific
data (LinkedIn URL, CSV path) will skip gracefully in non-TTY — the skill handles these
by running the CLI commands directly after setup completes.

**Step 4: After setup** — run data steps the skill collected inputs for:
```bash
# Import user's LinkedIn URL as owner profile (if collected)
linkedout setup-user-profile --url "https://linkedin.com/in/..."

# Import connections CSV (if collected)
linkedout import-connections ~/Downloads/Connections.csv
```

**Step 5: Verify** — source `agent-context.env` and check status:
```bash
source ~/linkedout-data/config/agent-context.env && linkedout status
```

**Critical instructions to include in the skill:**
- NEVER use raw SQL to insert data — always use the `linkedout` CLI or `linkedout setup`
- NEVER source `agent-context.env` before setup completes — setup creates it
- If setup hangs on a prompt, it's a bug in EOFError handling — report it

**Verify:** `/linkedout-setup` in Claude Code collects all inputs, writes config, runs
orchestrator, no EOFError, no raw SQL.

---

## Phase 4: Spec Updates

**File:** `docs/specs/onboarding-experience.md`

### 4a. Bootstrap behavior — under "Common Infrastructure (Steps 1-4)"

Add new behavior:

> **System record bootstrap after migrations**: Step 3 (Database Setup) bootstraps the
> system tenant (`tenant_sys_001`), business unit (`bu_sys_001`), and app user
> (`usr_sys_001`) via idempotent INSERTs (`ON CONFLICT DO NOTHING`) after Alembic
> migrations succeed. These records are FK targets for `connection.tenant_id`,
> `connection.bu_id`, `connection.app_user_id`, `enrichment_event.tenant_id`, and all
> RLS-scoped operations. Without them, CSV import and enrichment fail with FK violations.
> Verify the records exist after a fresh `linkedout setup` database step.

### 4b. Degradation behavior for optional keys — under "Full Setup Prompt Principles"

The spec documents costs for each key but doesn't state what degrades without them. Add:

> - **Without OpenAI key (local embeddings):** Search still works — the local nomic model
>   produces 768-dim embeddings vs OpenAI's 1536-dim. Quality is slightly lower for
>   nuanced queries, and generation takes ~0.2s/profile on CPU vs near-instant with OpenAI
>   Batch API. For networks under 5K profiles, the difference is marginal.
>
> - **Without Apify key (no enrichment):** LinkedOut works, but with stub profiles from
>   the CSV export (name, current company, current title, LinkedIn URL). No work history,
>   education, skills, or certifications. Affinity scoring falls back to connection-level
>   signals only (recency, company overlap) — career overlap and embedding similarity will
>   be zero. Queries like "who has ML experience?" depend on enriched profile data and will
>   return incomplete results.

### 4c. Non-TTY behavior — under "Implementation Conventions"

> - **EOFError handling in setup prompts**: Every `input()` and `getpass()` call in setup
>   modules wraps with `try/except (EOFError, KeyboardInterrupt)` and defaults to the
>   safe/conservative choice (keep existing config, skip optional steps). This enables
>   non-interactive execution via AI skills and CI pipelines. The pattern follows
>   `demo_offer.py` which already implements this correctly.

### 4d. Implementation conventions — new section before "Decisions"

> ### Implementation Conventions
>
> - **CLI entry point for subprocesses**: Setup modules invoke CLI commands via the
>   `linkedout` entry point (e.g., `subprocess.run(['linkedout', 'import-connections', ...])`),
>   never via `sys.executable -m linkedout.commands`. The entry point is installed by
>   `pip install -e backend/` and respects the active virtual environment.
>
> - **Timestamps in raw SQL**: Any raw SQL `INSERT` into tables derived from `BaseEntity`
>   must include `created_at` and `updated_at` with `NOW()`. These columns are NOT NULL
>   and use Python-side `default=` (not `server_default`), so PostgreSQL has no fallback
>   for raw SQL inserts. `is_active` and `version` are safe to omit (they have
>   `server_default`).
>
> - **Skill pre-configuration**: The `/linkedout-setup` skill collects all user inputs
>   conversationally before invoking `linkedout setup`. It writes `config.yaml` and
>   `secrets.yaml` so the orchestrator's existing config-present checks skip interactive
>   prompts. `agent-context.env` is not sourced before setup — setup creates it.

### 4e. Metadata updates

- Bump `version:` from 3 to 4
- Update `last_verified:` to `2026-04-10`
- Add `Updated:` line: "Added bootstrap, degradation behavior, non-TTY handling, implementation conventions"

---

## Phase 5: Tests

### 5a. Unit tests for `bootstrap_system_records()` (new)

**File:** `backend/tests/linkedout/setup/test_database.py` (extend existing)

Tests:
1. Bootstrap runs without error when tables exist and are empty
2. Idempotent — run twice, second run doesn't error or duplicate
3. FK ordering is correct (tenant before BU)
4. ON CONFLICT DO NOTHING when records already exist

Pattern: Mock `create_engine` and verify the 3 INSERT statements are executed in order.
Matches existing test patterns in this file.

### 5b. Unit tests for `load_csv_batch()` counter correctness (new)

**File:** `backend/tests/linkedout/commands/test_import_connections.py` (new or extend)

Tests:
1. Valid rows: counters sum to `total` (no double-counting)
2. `url_index` updated only after commit
3. Error on ConnectionEntity insert: `errors` increments, other counter does NOT
4. Duplicate URL in same batch: documented behavior (creates duplicate stub, caught by
   unique constraint)

Pattern: Use SQLAlchemy session with savepoint support. May need PostgreSQL integration
test if SQLite savepoint behavior differs.

### 5c. Regression test for `user_profile.py` timestamp fix (new)

**File:** `backend/tests/linkedout/setup/test_user_profile.py` (new or extend)

Test: Mock SQLAlchemy session, verify INSERT statement text includes `created_at` and
`updated_at`. This is a known failure mode (Python-side-only defaults) that warrants
a regression test.

### 5d. Verify existing tests pass after `sys.executable` change

After Phase 2b changes, run:
```bash
cd backend && python -m pytest tests/linkedout/setup/test_csv_import.py tests/linkedout/setup/test_contacts_import.py -v
```

Current tests use `"import-connections" in call_args` (not exact list equality), so they
should pass. But verify explicitly.

---

## Phase 6: Diagnostics Coverage Gaps

The `diagnostics.py` command (`linkedout diagnostics`) reports system health but has gaps
relevant to the issues we're fixing. These are not blockers but should be tracked.

**Currently covers:** profiles_total, profiles_with_embeddings, companies_total,
connections_total, last_enrichment, schema_version, API key config, DB connectivity,
disk space.

**Does NOT cover:**
- **Owner profile existence** — no check for `data_source='setup'` profile. After Issue
  10 fix, this is the user's identity anchor. Diagnostics should flag if missing.
- **Enrichment coverage** — no count of enriched vs stub profiles
  (`has_enriched_data=true` vs total). After Issue 13 fix, this tells users if Apify
  enrichment actually worked.
- **Affinity coverage** — the readiness report tracks this, but `diagnostics` doesn't.
  `connections_with_affinity / connections_total` is a key health metric.
- **Seed data status** — no check for whether seed tables are populated.

**Recommendation:** Add these to `get_db_stats()` in `health_checks.py` and surface
in the diagnostics output. Not in scope for this plan but should be a follow-up.

---

## Files Modified (Summary)

| File | What Changes |
|------|-------------|
| `backend/src/linkedout/setup/database.py` | Add `bootstrap_system_records()`, call after `verify_schema()` with guard |
| `setup` (repo root) | Line 285: append `\|\| true` to source command |
| `backend/src/linkedout/setup/user_profile.py` | Lines 138-141: add timestamps; wrap `input()` with EOFError handling |
| `backend/src/linkedout/setup/csv_import.py` | Line 189: `linkedout` CLI; remove `import sys`; wrap `input()` calls |
| `backend/src/linkedout/setup/contacts_import.py` | Line 156: `linkedout` CLI; remove `import sys`; wrap `input()` calls |
| `backend/src/linkedout/setup/auto_repair.py` | Line 160: `linkedout` CLI; remove `import sys`; wrap `input()` call |
| `backend/src/linkedout/setup/readiness.py` | Lines 409, 481: `linkedout` CLI; remove `import sys` |
| `backend/src/linkedout/setup/seed_data.py` | Lines 67, 118: `linkedout` CLI; remove `import sys`; wrap `input()` call |
| `backend/src/linkedout/setup/affinity.py` | Lines 47, 86: `linkedout` CLI; remove `import sys` |
| `backend/src/linkedout/setup/embeddings.py` | Lines 59, 171: `linkedout` CLI; remove `import sys`; wrap `input()` call |
| `backend/src/linkedout/setup/enrichment.py` | Lines 106, 178-179: use SYSTEM_TENANT/BU IDs; wrap `input()` call |
| `backend/src/linkedout/setup/api_keys.py` | Wrap all `input()`/`getpass()` calls with EOFError handling |
| `backend/src/linkedout/setup/skill_install.py` | Wrap `input()` call with EOFError handling |
| `backend/src/linkedout/commands/import_connections.py` | Lines 34-36: DRY fix; lines 112-176: defer counters |
| `skills/linkedout-setup/SKILL.md.tmpl` | Rewrite: collect-then-run, no pre-source, direct CLI for data steps |
| `skills/claude-code/linkedout-setup/SKILL.md` | Regenerate from template |
| `docs/specs/onboarding-experience.md` | Bootstrap, degradation, non-TTY, conventions, bump to v4 |
| `backend/tests/linkedout/setup/test_database.py` | Add bootstrap tests |
| `backend/tests/linkedout/commands/test_import_connections.py` | Add load_csv_batch tests |
| `backend/tests/linkedout/setup/test_user_profile.py` | Add timestamp regression test |

## Verification (End-to-End)

After all phases:

1. `./setup --auto` on fresh system -> exits 0
2. `linkedout setup --demo` on fresh DB -> system records exist, demo loads, no FK errors
3. `linkedout setup --full` with pre-written config.yaml + secrets.yaml -> EOFError on
   interactive prompts defaults gracefully, all 15 steps complete
4. CSV import with N-row file -> `total=N`, no double-counting, profiles in DB
5. Enrichment -> `enrichment_event.tenant_id = 'tenant_sys_001'`, no FK violation
6. `/linkedout-setup` in Claude Code -> collects inputs conversationally, writes config,
   runs orchestrator, no EOFError, no raw SQL
7. All existing tests pass: `pytest tests/linkedout/setup/ -v`
8. New tests pass: bootstrap idempotency, CSV counter correctness, timestamp regression

## Review Notes

Corrections applied during architect review:
- **Table name:** `bu` not `business_unit` — `BuEntity.__tablename__ = 'bu'`
- **`server_default` vs `default`:** `created_at`/`updated_at` use Python-side `default=`
  only, confirming raw SQL must include them. `is_active`/`version` have `server_default`,
  safe to omit.
- **`app_user_tenant_role` NOT needed:** CSV import and enrichment don't FK to this table.
  Bootstrap is minimal — only records that cause FK violations if missing.
- **Duplicate URL edge case in Issue 12 fix:** Documented and accepted — better than
  current behavior of 0 imports.
- **Skill template path:** Source is `skills/linkedout-setup/SKILL.md.tmpl`, generated
  output is `skills/claude-code/linkedout-setup/SKILL.md`. Template uses mustache vars
  like `{{AGENT_CONTEXT_PATH}}`, `{{CLI_PREFIX}}`, `{{DATA_DIR}}`, `{{CONFIG_DIR}}`.

Plan review items folded in (from `plan-review-setup-flow-bugfix.md`):
- **#2:** Bootstrap guarded behind schema verification success
- **#4:** Verified — orchestrator reads `secrets.yaml` via `YamlSecretsSource` in
  `shared/config/yaml_sources.py`, and `_read_existing_secrets()` in `api_keys.py`.
  Path is `~/linkedout-data/config/secrets.yaml`. HOWEVER: even with existing keys,
  `collect_api_keys()` still calls `input()` for "Replace it?" — solved by Phase 3a
  EOFError handling.
- **#6:** All 7 files explicitly listed with `import sys` removal decision
- **#7:** DRY violation in `import_connections.py:34-36` added to Phase 2d scope
- **#8:** Bootstrap unit tests added as Phase 5a
- **#9:** `load_csv_batch()` unit tests added as Phase 5b
- **#10:** Existing test verification added to Phase 5d
- **#11:** Timestamp regression test added as Phase 5c

# SP-specs: Spec Updates

## Context

Read `_shared_context.md` first.

This plan modifies behaviors documented in existing specs. Spec updates can run in parallel
with any implementation phase — they document the intended behavior, not the implementation.

## Depends On

None (can run in parallel with any phase). However, the spec content describes behaviors
implemented in SP01, SP02a, SP02b, and the skill rewrites.

## Tasks

### Update `docs/specs/cli_commands.collab.md` (v3 -> v4)

1. **`diagnostics` command** — Add `health_status` (object: `{badge, critical, warning, info}`)
   and `issues` (list of `{severity, category, message, action}`) to JSON output. Badge values:
   HEALTHY, NEEDS_ATTENTION, ACTION_REQUIRED. Document `compute_issues()` logic (lives in
   health_checks.py).

2. **`diagnostics --repair`** — Change subprocess from `sys.executable -m linkedout.cli embed`
   to `linkedout embed`. Document that repair uses the installed CLI entry point.

3. **`config show`** — Change from "Not yet implemented" to full behavior: outputs
   `embedding_provider`, `embedding_model`, `database_url` (masked), `data_dir`, `demo_mode`,
   `api_keys.openai` (configured/not configured), `api_keys.apify` (configured/not configured).
   Supports `--json` flag.

4. **`log-query`** (new command) — Document the new CLI command: `linkedout log-query <text>
   --type <type> --results <count>`. Types: company_lookup, person_search, semantic_search,
   network_stats, general.

### Update `docs/specs/skills_system.collab.md` (v2 -> v3)

1. **`/linkedout-setup-report`** — Rewrite catalog entry. Remove "Compute health score" from
   skill (CLI does it now). Change filenames from `setup-report-*` to `diagnostic-*`. Remove
   cost tracking section.

2. **`/linkedout-report`** — Rewrite catalog entry. Remove Cost Tracker section and Profile
   Freshness by `enriched_at`. Add "degrades gracefully when query history is empty."

3. **`/linkedout-history`** — Simplify catalog entry. Note dependency on query logging from
   `/linkedout` skill.

4. **`/linkedout`** — Add "Query Logging" section documenting post-query `log_query()` call.
   Add graceful degradation behavior (missing agent-context.env, 0 profiles, 0 embeddings,
   demo mode). Add `linkedout config --json` fallback for config reference.

5. **`/linkedout-extension-setup`** — Add experimental disclaimer behavior. Add dynamic port
   detection behavior.

6. **`/linkedout-upgrade`** — Add dirty-state check behavior. Add post-pull changelog display.

### Bump versions

- `cli_commands.collab.md`: bump version from v3 to v4
- `skills_system.collab.md`: bump version from v2 to v3

## Verification

```bash
# Specs parse as valid markdown
python3 -c "
import pathlib
for f in ['docs/specs/cli_commands.collab.md', 'docs/specs/skills_system.collab.md']:
    p = pathlib.Path(f)
    assert p.exists(), f'{f} not found'
    content = p.read_text()
    assert 'version' in content.lower(), f'{f} missing version'
    print(f'{f}: OK')
"
```

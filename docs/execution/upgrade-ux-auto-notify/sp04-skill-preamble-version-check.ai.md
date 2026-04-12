# Sub-phase 04: Skill Preamble Version Check

## Metadata

| Field | Value |
|-------|-------|
| Sub-phase | SP04 |
| Dependencies | SP02 (needs `--check --json` flag on `linkedout version`) |
| Estimated effort | 1 session (~1.5 hours) |
| Branch | main |
| Plan reference | `docs/plan/2026-04-12-upgrade-ux-auto-notify-holistic.collab.md` — Sub-phase 4 |
| Shared context | `_shared_context.md` |

## Objective

The `/linkedout` skill preamble includes a version check step. When an update is available, the skill shows a notification after the health check, before answering the query. The notification matches the CLI banner format for consistency (but says `/linkedout-upgrade` instead of `linkedout upgrade`).

## Context

The `/linkedout` skill template at `skills/linkedout/SKILL.md.tmpl` has a Preamble section with numbered steps. Step 1 loads credentials, step 2 checks system health. We add a step 3 that runs `linkedout version --check --json` and shows a notification if an update is available.

The `--check --json` flag is added by SP02. This sub-phase depends on SP02 being complete.

## Tasks

### 1. Add version check step to skill template

**File:** `skills/linkedout/SKILL.md.tmpl`

After step 2 (Check system health), add:

```markdown
3. **Check for updates (silent):**

```bash
UPDATE_JSON=$({{CLI_PREFIX}} version --check --json 2>/dev/null)
```

If the command succeeds and the JSON contains `"update_available": true`, show:
> LinkedOut v{latest} available (you have v{current}). Run /linkedout-upgrade to update.

If the command fails or returns an error, skip silently and proceed to the query. Do NOT let a failed version check block the user's query.
```

Key details:
- Uses `{{CLI_PREFIX}} version --check --json` (the flag from SP02)
- Redirects stderr to /dev/null so network errors are invisible
- The skill context uses `/linkedout-upgrade` (skill invocation), not `linkedout upgrade` (CLI command)
- The step is **after** the health check and **before** the query routing
- Explicit instruction: "If the version check command fails or returns an error, skip silently and proceed to the query"

### 2. Update step numbering

After inserting step 3, verify that any subsequent steps are renumbered correctly. Currently the template goes:

1. Load credentials + activate venv
2. Check system health
3. *(new)* Check for updates (silent)

The "Schema Reference" and "Query Routing" sections follow the Preamble and don't have numbered steps that conflict.

### 3. Regenerate skill files

Run `bin/generate-skills` to compile the template change into all host-specific output directories:

```bash
cd $(git rev-parse --show-toplevel) && bin/generate-skills
```

This regenerates:
- `skills/claude-code/linkedout/SKILL.md`
- `skills/codex/linkedout/SKILL.md`
- `skills/copilot/linkedout/SKILL.md`

(And all other skill templates, but only the `/linkedout` one changes.)

### 4. Verify regenerated files

After regeneration, spot-check one output file to confirm:
- The version check step is present
- `{{CLI_PREFIX}}` was replaced with the host-specific CLI prefix
- The step numbering is correct
- No template syntax errors

```bash
# Check claude-code output
grep -A 5 "Check for updates" skills/claude-code/linkedout/SKILL.md

# Check codex output
grep -A 5 "Check for updates" skills/codex/linkedout/SKILL.md
```

## Verification

```bash
# Regenerate and check for errors
cd $(git rev-parse --show-toplevel) && bin/generate-skills

# Verify the version check step exists in all three outputs
for host in claude-code codex copilot; do
  echo "=== $host ==="
  grep -c "version --check --json" skills/$host/linkedout/SKILL.md
done

# Each should print "1" (one match per file)
```

No unit test needed for this sub-phase — it's a template change. The version check command itself is tested in SP02. The skill regeneration is verified by `bin/generate-skills` running without error and spot-checking output.

## What NOT to Do

- Do not add version comparison logic inline in the template — use `--check --json` from SP02
- Do not modify `update_checker.py` — that's SP01/SP02/SP03
- Do not modify the `/linkedout-upgrade` skill template — that's SP05
- Do not update specs — that's bundled into SP05
- Do not make the version check blocking — if it fails, the skill must proceed normally

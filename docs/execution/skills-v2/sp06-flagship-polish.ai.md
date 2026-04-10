# SP06: Polish the Flagship — `/linkedout` Improvements

## Context

Read `_shared_context.md` first.

The main query skill works but has rough edges: references a config command that was a stub,
fails hard when `agent-context.env` is missing, and gives no guidance when the system is empty.

## Depends On

- **SP01** (extended diagnostics for health gating)
- **SP02b** (`linkedout config show --json` is implemented)

## Tasks

### 6a. Fix `linkedout config show` reference

**File:** `skills/linkedout/SKILL.md.tmpl`

After SP02b adds the command, update the config reference to use `--json` flag with fallback:

```markdown
Check the configured embedding provider:
\```bash
linkedout config show --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['embedding_provider'])" 2>/dev/null || echo "local"
\```
```

### 6b. Add graceful degradation to the preamble

Current preamble fails hard if `agent-context.env` doesn't exist. Add a softer check:

```markdown
If `agent-context.env` does not exist but `linkedout status --json` works (database_url is
configured via environment):
> Running without agent-context.env. Some features may be limited. Run `/linkedout-setup` for full configuration.
```

### 6c. Improve the health check gate

Make the status check smarter with contextual messages:

- If 0 profiles: "Your network is empty. Run `/linkedout-setup` to import your connections."
- If 0 embeddings but profiles > 0: "Semantic search unavailable — run `linkedout embed` first. Structured queries (by company, role, location) still work."
- If demo mode: "Running in demo mode with sample data. Run `/linkedout-setup` to switch to your real network."

These messages set expectations so the user isn't confused when semantic search returns nothing.

**Active empty-state guidance (Review Decision #7).**

## Verification

```bash
bin/generate-skills

# Manual QA:
# /linkedout with no agent-context.env -> degradation message, not error
# /linkedout with 0 profiles -> "network is empty" message
# /linkedout with 0 embeddings -> "semantic search unavailable" message
```

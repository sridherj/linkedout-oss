# SP07: Polish `/linkedout-extension-setup`

## Context

Read `_shared_context.md` first for skill template conventions.

The Chrome extension is not thoroughly tested. The skill works but needs an experimental
disclaimer and should read the backend port from config rather than hardcoding.

## Depends On

None (independent). However, uses `linkedout config show --json` from SP02b if available —
should fall back to hardcoded port 8001 if the command doesn't exist yet.

## Tasks

### 7a. Add experimental disclaimer

**File:** `skills/linkedout-extension-setup/SKILL.md.tmpl`

Add a prominent note at the top of the skill (after the preamble):

```markdown
> **Note:** The Chrome extension is experimental and not thoroughly tested. You may encounter
> rough edges. Core LinkedOut functionality (setup, queries, reports) works without the extension.
```

### 7b. Improve backend port detection

Current skill hardcodes `localhost:8001`. Read the port from config with fallback:

```bash
PORT=$(linkedout config show --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('backend_port', 8001))" 2>/dev/null || echo 8001)
```

Use `$PORT` instead of hardcoded `8001` throughout the template.

## Verification

```bash
bin/generate-skills

# Check generated skill contains disclaimer
grep -i "experimental" skills/claude-code/linkedout-extension-setup/SKILL.md

# Check port detection
grep "PORT=" skills/claude-code/linkedout-extension-setup/SKILL.md
```

# SP09: Regenerate All Skills + Validate

## Context

Read `_shared_context.md` first.

All template changes from SP02a, SP03-SP08 need to be compiled into per-host output.
This is the final sub-phase — run only after all template changes are complete.

## Depends On

- **All template sub-phases:** SP02a, SP03, SP04, SP05, SP06, SP07, SP08

## Tasks

### 9a. Regenerate all skills

```bash
bin/generate-skills
```

Verify all 3 hosts (Claude Code, Codex, Copilot) get updated output.

### 9b. Run check mode

```bash
bin/generate-skills --check
```

Verify generated files match templates (CI parity check).

### 9c. Spot-check each host output

For each host, verify:
- No unresolved `{{variables}}` in any SKILL.md
- Frontmatter parses correctly (especially Codex allowlist mode)
- Path rewrites applied (`.claude/skills/` -> `.agents/skills/` for Codex)
- Tool rewrites applied (`AskUserQuestion` -> `input` for Codex)

```bash
# Check for unresolved variables
grep -r '{{' skills/claude-code/ skills/codex/ skills/copilot/ --include='*.md' | grep -v '```' | head -20

# Verify all expected skill directories exist per host
for host in claude-code codex copilot; do
  echo "=== $host ==="
  ls skills/$host/
done
```

## Verification

```bash
# CI parity
bin/generate-skills --check && echo "PASS" || echo "FAIL"

# No unresolved vars (excluding code blocks)
! grep -rP '\{\{[A-Z_]+\}\}' skills/claude-code/ skills/codex/ skills/copilot/ --include='*.md'
```

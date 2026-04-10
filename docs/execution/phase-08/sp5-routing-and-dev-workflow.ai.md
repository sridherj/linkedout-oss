# Sub-Phase 5: Routing + Dev Workflow

**Phase:** 8 — Skill System & Distribution
**Plan tasks:** 8I (CLAUDE.md / AGENTS.md Routing), 8K (Dev Workflow)
**Dependencies:** sp4 (Generation Script — must be working)
**Blocks:** —
**Can run in parallel with:** —

## Objective
Create the routing files that tell AI hosts when to invoke LinkedOut skills, and the developer workflow scripts for contributing to skills. This is the final sub-phase — after this, the skill system is complete and ready for manual QA.

## Context
- Read shared context: `docs/execution/phase-08/_shared_context.md`
- Read plan (8I + 8K sections): `docs/plan/phase-08-skill-system.md`
- Read all generated skill files from sp4 (for skill names and descriptions)
- Read CLI surface decision: `docs/decision/cli-surface.md`
- Reference gstack's CLAUDE.md: `<reference>/gstack/.claude/` (for routing patterns)

## Deliverables

### Part A: Routing (8I)

#### 1. `skills/routing/ROUTING.md.tmpl` (NEW)

Routing template that generates host-specific routing files. The routing file tells the AI host about available LinkedOut skills and when to invoke them.

**Structure:**
```markdown
# LinkedOut Skills

LinkedOut provides AI-powered access to your professional network data.

## Available Skills

### /linkedout — Network Query
Invoke when the user asks about their professional network, connections, companies, roles, or LinkedIn data.
**Trigger patterns:** "who do I know at...", "find people who...", "my network", "connections at...", "LinkedIn", "people at [company]", "engineers in [location]", "warm intros to..."

### /linkedout-setup — First-Time Setup
Invoke when the user asks to set up or install LinkedOut.
**Trigger patterns:** "set up LinkedOut", "install LinkedOut", "configure LinkedOut", "get started with LinkedOut"

### /linkedout-upgrade — Upgrade
Invoke when the user asks to upgrade or update LinkedOut.
**Trigger patterns:** "upgrade LinkedOut", "update LinkedOut", "new version of LinkedOut"

### /linkedout-history — Query History
Invoke when the user asks about past queries or search history.
**Trigger patterns:** "LinkedOut history", "past searches", "previous queries", "what did I search"

### /linkedout-report — Usage Report
Invoke when the user asks for network stats or usage reports.
**Trigger patterns:** "LinkedOut report", "network stats", "how many connections", "LinkedOut usage"

### /linkedout-setup-report — System Health
Invoke when the user asks for system diagnostics or a health check.
**Trigger patterns:** "LinkedOut diagnostics", "system health", "LinkedOut status", "troubleshoot LinkedOut"
```

**Host-specific rendering:**
- For Claude Code → generates `skills/claude-code/CLAUDE.md` with Claude Code skill path references
- For Codex → generates `skills/codex/AGENTS.md` with Codex-appropriate format
- For Copilot → generates `skills/copilot/COPILOT.md` with Copilot-appropriate format
- Use `{{#if HOST_NAME == "..."}}`  conditionals for host-specific sections
- Skill paths reference `{{LOCAL_SKILL_PATH}}` so they resolve correctly per host

#### 2. Update `bin/generate-skills` to generate routing files

The generation script (from sp4) should also render the routing template alongside skill templates. Add:
- Discover `skills/routing/ROUTING.md.tmpl`
- Render for each host
- Write to:
  - `skills/claude-code/CLAUDE.md`
  - `skills/codex/AGENTS.md`
  - `skills/copilot/COPILOT.md`

### Part B: Dev Workflow (8K)

#### 3. `bin/dev-setup` (NEW)

Dev symlink setup script. Python, executable.

**Behavior:**
1. Detect installed AI hosts by checking for directories:
   - Claude Code: `~/.claude/` exists → host is available
   - Codex: `~/.agents/` exists → host is available
   - Copilot: `~/.github/` exists → host is available
2. For each detected host:
   - Create the skill directory if it doesn't exist (e.g., `~/.claude/skills/linkedout/`)
   - Symlink the repo's generated output into the host's skill directory
   - Example: `~/.claude/skills/linkedout/` → symlink to `<repo>/skills/claude-code/linkedout/`
   - Also symlink the routing file (CLAUDE.md → repo's generated CLAUDE.md)
3. Report what was linked: "Linked 6 skills + routing for Claude Code"
4. Idempotent: if symlinks already exist and point to the right place, skip with a message. If they point to the wrong place, warn and offer to fix.

**Safety:**
- Never overwrite non-symlink files (warn and skip)
- Never create symlinks outside of known skill directories
- Always confirm the target directory before creating symlinks

#### 4. `bin/dev-teardown` (NEW)

Dev symlink teardown script. Python, executable.

**Behavior:**
1. For each host (Claude Code, Codex, Copilot):
   - Find symlinks in the host's skill directory that point into this repo
   - Remove those symlinks
   - Do NOT remove non-symlink files (safety)
2. Report what was unlinked: "Unlinked 6 skills + routing for Claude Code"
3. Idempotent: if no symlinks exist, report "Nothing to unlink"

#### 5. `linkedout-relink` CLI command

Add to the LinkedOut CLI (via `backend/pyproject.toml` entry point or as a standalone `bin/` script).

**Behavior:**
1. Check if skill symlinks exist for each detected host
2. For each symlink:
   - Verify the target exists (symlink not broken)
   - If broken: fix by re-creating symlink to the correct path
   - If missing: report as "not linked" (don't auto-create — that's `dev-setup`'s job)
3. Report status: "Claude Code: 6 skills linked (all valid)"

**Design decision:** Implement as `bin/linkedout-relink` (standalone script), NOT as a `linkedout relink` CLI subcommand. This is a dev convenience, not a user-facing command. Keep it out of the main CLI help.

#### 6. Update `CONTRIBUTING.md`

Add a "Skill Development" section:
```markdown
## Skill Development

### Setup dev environment
```bash
bin/dev-setup    # Symlinks skills into your AI host
```

### Edit skills
1. Edit template files in `skills/*/SKILL.md.tmpl`
2. Run `bin/generate-skills` to regenerate
3. Changes are immediately available in your AI host (via symlinks)

### Teardown
```bash
bin/dev-teardown  # Removes skill symlinks
```

### Fix broken links
```bash
bin/linkedout-relink  # Detects and fixes broken symlinks
```
```

## Verification

### Routing
1. `skills/routing/ROUTING.md.tmpl` exists
2. `python bin/generate-skills` generates routing files:
   - `skills/claude-code/CLAUDE.md` exists
   - `skills/codex/AGENTS.md` exists
   - `skills/copilot/COPILOT.md` exists
3. Routing files reference correct skill paths for each host
4. `python bin/generate-skills --check` still passes (routing files included in check)

### Dev Workflow
5. `python bin/dev-setup` succeeds and reports linked skills (at least for Claude Code, which is likely installed)
6. Verify symlinks exist: `ls -la ~/.claude/skills/linkedout/` shows symlink
7. `python bin/dev-teardown` succeeds and reports unlinked skills
8. Verify symlinks removed: `ls -la ~/.claude/skills/linkedout/` shows no symlinks (or directory doesn't exist)
9. Create a broken symlink → `python bin/linkedout-relink` detects and fixes it
10. `python bin/dev-setup` is idempotent: run twice, second run reports "already linked"

### Manual QA
11. With skills linked via `bin/dev-setup`, ask Claude Code "who do I know at Stripe?" → should invoke `/linkedout`
12. Ask "set up LinkedOut" → should invoke `/linkedout-setup`

## Notes
- Routing files are the "discoverability" layer. Without them, users have to know about `/linkedout` to use it. With them, AI hosts automatically suggest LinkedOut for relevant queries.
- Dev workflow scripts assume the repo is the source of truth. `bin/dev-setup` creates symlinks FROM the host's skill directory TO the repo. This means changes to generated files in the repo are immediately reflected.
- `bin/dev-teardown` is important for clean uninstall — don't want stale skill files hanging around in `~/.claude/skills/`.
- `linkedout-relink` handles the "I moved the repo" case. After `mv ~/projects/linkedout .`, symlinks break. `linkedout-relink` fixes them without needing to `dev-teardown` + `dev-setup`.
- The Codex and Copilot routing formats may need adjustment as those platforms evolve. Flag Copilot as "beta" per decision #2.

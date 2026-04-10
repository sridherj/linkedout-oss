# Sub-Phase 3: Stub Skills (Setup, Upgrade, History, Report, Setup-Report)

**Phase:** 8 — Skill System & Distribution
**Plan tasks:** 8D (/linkedout-setup), 8E (/linkedout-upgrade), 8F (/linkedout-history), 8G (/linkedout-report), 8H (/linkedout-setup-report)
**Dependencies:** sp1 (Template Engine + Host Configs)
**Blocks:** sp4
**Can run in parallel with:** sp2

## Objective
Create all 5 stub skill templates. These are working skill files with minimal content — the full interactive flows will be built in Phases 9-11. Each stub explains what the skill does, lists prerequisites, and provides basic functionality where possible.

## Context
- Read shared context: `docs/execution/phase-08/_shared_context.md`
- Read plan (8D-8H sections): `docs/plan/phase-08-skill-system.md`
- Read CLI surface decision: `docs/decision/cli-surface.md` (for command names referenced in stubs)
- Read env config decision: `docs/decision/env-config-design.md`

## Deliverables

### 1. `skills/linkedout-setup/SKILL.md.tmpl` (NEW)

**Frontmatter:**
```yaml
---
name: linkedout-setup
description: Set up LinkedOut — install dependencies, configure database, and import your LinkedIn data
tools:
  - Bash
  - Read
  - Write
---
```

**Stub body:**
- Explain what setup does: installs dependencies, creates DB, configures env, imports LinkedIn export
- List prerequisites: Python 3.11+, PostgreSQL with pgvector, LinkedIn data export
- Point to `CONTRIBUTING.md` for manual setup steps
- Note: "Full interactive setup flow coming in a future release. For now, follow the manual steps below."
- Include basic commands the user can run manually: `{{CLI_PREFIX}} status`, `{{CLI_PREFIX}} diagnostics`
- Reference `{{DATA_DIR}}` and `{{CONFIG_DIR}}` for path context

### 2. `skills/linkedout-upgrade/SKILL.md.tmpl` (NEW)

**Frontmatter:**
```yaml
---
name: linkedout-upgrade
description: Upgrade LinkedOut to the latest version — run migrations, update config, and verify system health
tools:
  - Bash
  - Read
---
```

**Stub body:**
- Explain what upgrade does: pulls latest code, runs DB migrations, updates config, verifies health
- Show version check logic: `{{CLI_PREFIX}} status --json` to get current version
- Point to manual upgrade steps
- Note: "Full interactive upgrade flow coming in a future release."
- Include `{{CLI_PREFIX}} diagnostics` for post-upgrade verification

### 3. `skills/linkedout-history/SKILL.md.tmpl` (NEW)

**Frontmatter:**
```yaml
---
name: linkedout-history
description: Browse your LinkedOut query history — see past searches and revisit results
tools:
  - Bash
  - Read
---
```

**Stub body:**
- Explain query history: reads from `{{DATA_DIR}}queries/` JSONL files
- Show how to list recent queries
- Show how to replay a past query
- Note: "Full history browsing and analytics coming in a future release."

### 4. `skills/linkedout-report/SKILL.md.tmpl` (NEW)

**Frontmatter:**
```yaml
---
name: linkedout-report
description: Generate LinkedOut usage reports — network stats, query patterns, and system health
tools:
  - Bash
  - Read
---
```

**Stub body:**
- Explain what reports are available: network stats, query frequency, system health
- Run `{{CLI_PREFIX}} status` for basic network stats
- Run `{{CLI_PREFIX}} diagnostics` for system health
- Note: "Full reporting and analytics coming in a future release."

### 5. `skills/linkedout-setup-report/SKILL.md.tmpl` (NEW)

**Frontmatter:**
```yaml
---
name: linkedout-setup-report
description: Generate a LinkedOut system health report for sharing or troubleshooting
tools:
  - Bash
  - Read
---
```

**Stub body:**
- Explain purpose: generates a shareable diagnostic report for troubleshooting
- Run `{{CLI_PREFIX}} diagnostics` and format output
- Include system info: Python version, DB connection status, data directory location
- Format for easy copy-paste or sharing
- Note: "Full diagnostic reporting coming in a future release."

### Common patterns across all stubs:

- All stubs use `{{CLI_PREFIX}}` for command references (resolves to `linkedout`)
- All stubs use `{{DATA_DIR}}` and `{{CONFIG_DIR}}` for path references
- All stubs load `{{AGENT_CONTEXT_PATH}}` in the preamble for DB credentials
- All stubs include a "Phase N will replace this stub" note (so future contributors know these are intentional placeholders)
- Keep each stub concise — 30-60 lines of template content. These are placeholders, not full implementations.

### Important: Do NOT create `/linkedout-extension-setup`
Per decision #6: extension setup skill is created in Phase 12 after UX design gate. No stubs, no placeholders.

## Verification
1. All 5 template files exist:
   - `skills/linkedout-setup/SKILL.md.tmpl`
   - `skills/linkedout-upgrade/SKILL.md.tmpl`
   - `skills/linkedout-history/SKILL.md.tmpl`
   - `skills/linkedout-report/SKILL.md.tmpl`
   - `skills/linkedout-setup-report/SKILL.md.tmpl`
2. Each template renders without errors for all 3 hosts:
   ```python
   from skills.lib.template import render_template_file
   from skills.lib.config import load_host_config, get_global_context
   import glob
   for tmpl in glob.glob("skills/*/SKILL.md.tmpl"):
       for host in ["claude", "codex", "copilot"]:
           config = load_host_config(host)
           ctx = get_global_context()
           result = render_template_file(tmpl, config, ctx)
           assert "{{" not in result, f"Unresolved variable in {tmpl} for {host}"
   ```
3. No unresolved `{{variables}}` in any rendered output
4. Each stub has valid YAML frontmatter with `name`, `description`, and `tools` fields
5. Exactly 5 stub skills — NOT 6 (no extension-setup)

## Notes
- These stubs are intentionally minimal. Resist the urge to build out full functionality — that's Phases 9-11.
- Each stub should still be useful — a user who invokes it should get helpful guidance, not just "coming soon."
- The stubs establish the file structure and naming conventions that Phases 9-11 will fill in.

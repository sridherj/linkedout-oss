# Sub-Phase 1: Template Engine + Host Configs

**Phase:** 8 — Skill System & Distribution
**Plan tasks:** 8A (SKILL.md Template System), 8B (Host Configs)
**Dependencies:** Phase 7 (Seed Data Pipeline), Phase 6 (Code Cleanup — `linkedout` CLI namespace must be final)
**Blocks:** sp2, sp3
**Can run in parallel with:** —

## Objective
Build the template engine that renders `SKILL.md.tmpl` files into host-specific `SKILL.md` files, and define the per-host configuration for Claude Code, Codex, and Copilot. This is the foundation — all other sub-phases depend on the template engine and host configs being in place.

## Context
- Read shared context: `docs/execution/phase-08/_shared_context.md`
- Read plan (8A + 8B sections): `docs/plan/phase-08-skill-system.md`
- Read config design decision: `docs/decision/env-config-design.md`
- Read skill distribution pattern: `docs/decision/2026-04-07-skill-distribution-pattern.md`
- Reference gstack's skill infrastructure: `<reference>/gstack/hosts/` (for config shape)

## Deliverables

### 1. `skills/lib/__init__.py` (NEW)
Package init. Export the main public API:
```python
from skills.lib.template import render_template
from skills.lib.config import load_host_config, get_global_context
from skills.lib.frontmatter import process_frontmatter
```

### 2. `skills/lib/template.py` (NEW)

Template engine with these capabilities:

**Variable resolution:**
- `{{VARIABLE_NAME}}` syntax — resolve from host config + global context
- Fail with a clear error if a variable is unresolved (no silent empty strings)

**Conditional blocks:**
- `{{#if HOST_NAME == "claude"}}...{{/if}}` for host-specific content
- `{{#if HOST_NAME != "codex"}}...{{/if}}` for negation
- Keep it simple — no nested conditionals, no loops, no complex expressions

**Template loading:**
- `load_template(path: str) -> str` — read a `.tmpl` file
- `render_template(template: str, variables: dict) -> str` — resolve all variables and conditionals
- `render_template_file(tmpl_path: str, host_config: dict, global_context: dict) -> str` — full pipeline

**Design constraints:**
- Python-based. Use `string.Template` style or lightweight regex-based approach. No heavy template engines (no full Jinja2).
- Deterministic output — same input always produces same output
- No external dependencies beyond Python stdlib

### 3. `skills/lib/config.py` (NEW)

Host config loader and global context:

**`load_host_config(host_name: str) -> dict`**
- Load from `skills/hosts/{host_name}.yaml`
- Validate required fields: `name`, `display_name`, `skill_install_path`, `local_skill_path`, `frontmatter`, `path_rewrites`, `tool_rewrites`
- Raise clear error if config file missing or invalid

**`list_hosts() -> list[str]`**
- Return list of available hosts by scanning `skills/hosts/*.yaml`

**`get_global_context() -> dict`**
- Return global template variables: `VERSION`, `DATA_DIR`, `CONFIG_DIR`, `CLI_PREFIX`, `AGENT_CONTEXT_PATH`
- Read version from `backend/pyproject.toml` or a `VERSION` file
- `DATA_DIR` = `~/linkedout-data/`
- `CONFIG_DIR` = `~/linkedout-data/config/`
- `AGENT_CONTEXT_PATH` = `~/linkedout-data/config/agent-context.env`
- `CLI_PREFIX` = `linkedout`

**`get_host_variables(host_config: dict, global_context: dict) -> dict`**
- Merge host-specific variables with global context
- Add `HOST_NAME`, `DISPLAY_NAME`, `SKILL_INSTALL_PATH`, `LOCAL_SKILL_PATH`

### 4. `skills/lib/frontmatter.py` (NEW)

Frontmatter processing per host rules:

**`process_frontmatter(frontmatter: str, host_config: dict) -> str`**
- Parse YAML frontmatter (between `---` delimiters)
- Apply host config rules:
  - `denylist` mode: strip listed fields
  - `allowlist` mode: only keep listed fields
  - `description_limit`: truncate description field to N characters
- Re-serialize to YAML frontmatter

**`split_frontmatter(content: str) -> tuple[str, str]`**
- Split markdown file into frontmatter and body

**`join_frontmatter(frontmatter: str, body: str) -> str`**
- Rejoin frontmatter and body with `---` delimiters

### 5. `skills/hosts/claude.yaml` (NEW)
```yaml
name: claude
display_name: Claude Code
skill_install_path: ~/.claude/skills/linkedout
local_skill_path: .claude/skills/linkedout
frontmatter:
  mode: denylist
  strip_fields: []
  description_limit: null
path_rewrites: []
tool_rewrites: {}
```

### 6. `skills/hosts/codex.yaml` (NEW)
```yaml
name: codex
display_name: Codex
skill_install_path: ~/.agents/skills/linkedout
local_skill_path: .agents/skills/linkedout
frontmatter:
  mode: allowlist
  keep_fields:
    - name
    - description
  description_limit: 200
path_rewrites:
  - from: ".claude/skills/"
    to: ".agents/skills/"
tool_rewrites:
  AskUserQuestion: input
```

### 7. `skills/hosts/copilot.yaml` (NEW)
```yaml
name: copilot
display_name: GitHub Copilot
skill_install_path: ~/.github/skills/linkedout
local_skill_path: .github/skills/linkedout
frontmatter:
  mode: denylist
  strip_fields: []
  description_limit: null
path_rewrites:
  - from: ".claude/skills/"
    to: ".github/skills/"
tool_rewrites: {}
```

### 8. Unit Tests

**`tests/skills/__init__.py`** (NEW) — empty test package init

**`tests/skills/test_template.py`** (NEW)
- Variable resolution: `{{FOO}}` with `{"FOO": "bar"}` → `"bar"`
- Unresolved variable raises error
- Conditional: `{{#if HOST_NAME == "claude"}}visible{{/if}}` resolves correctly
- Negated conditional: `{{#if HOST_NAME != "codex"}}visible{{/if}}` resolves correctly
- Conditional block removed when condition is false

**`tests/skills/test_frontmatter.py`** (NEW)
- Denylist mode strips specified fields
- Allowlist mode keeps only specified fields
- Description limit truncates correctly
- Round-trip: split → process → join preserves body content

**`tests/skills/test_config.py`** (NEW)
- `load_host_config("claude")` returns valid config with all required fields
- `list_hosts()` returns `["claude", "codex", "copilot"]`
- `get_global_context()` includes all expected keys
- Missing host config raises clear error

## Verification
1. `cd /path/to/project && python -c "from skills.lib.template import render_template; print(render_template('Hello {{NAME}}', {'NAME': 'World'}))"` prints `Hello World`
2. `cd /path/to/project && python -c "from skills.lib.config import load_host_config; c = load_host_config('claude'); print(c['display_name'])"` prints `Claude Code`
3. `pytest tests/skills/test_template.py -v` passes
4. `pytest tests/skills/test_frontmatter.py -v` passes
5. `pytest tests/skills/test_config.py -v` passes

## Notes
- The template engine should be minimal — just variable substitution and basic conditionals. If you find yourself building complex features, you've gone too far.
- Host configs are YAML (not TypeScript like gstack) because this is a Python project.
- PyYAML is likely already a dependency (used by pydantic-settings or similar). Check `backend/requirements.txt` before adding it. If not present, add it.
- The `skills/` directory is at the repo root, not inside `backend/`. Skills are a cross-cutting concern.
- Tests go in `tests/skills/` at the repo root, not `backend/tests/` — these test the skill infrastructure, not backend code.

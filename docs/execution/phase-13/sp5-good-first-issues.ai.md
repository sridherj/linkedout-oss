# SP5: Good First Issues

**Phase:** 13 — Polish & Launch
**Sub-phase:** 5 of 6
**Dependencies:** SP1 (roadmap — issues reference project direction), SP2 (docs — issues reference documentation)
**Estimated effort:** ~45 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Create 5-10 GitHub issues labeled `good first issue` that are approachable for new contributors. Each issue must be self-contained with clear scope, acceptance criteria, and pointers to relevant code.

**Tasks from phase plan:** 13F

---

## Task 13F: Good First Issues

### Required reading before creating issues

Read these files to ensure issues reference accurate code locations:
- `backend/src/linkedout/cli.py` (or wherever Click commands are defined) — CLI command implementations
- `backend/src/shared/config/` — Configuration system
- `extension/entrypoints/sidepanel/` — Extension side panel code
- `docs/configuration.md` (from SP2) — Config documentation

### Issues to create (via `gh issue create`)

Create each issue using the template format below. Use `gh issue create` with `--label` flags.

First, ensure the required labels exist:
```bash
gh label create "good first issue" --description "Good for newcomers" --color 7057ff 2>/dev/null || true
gh label create "enhancement" --color a2eeef 2>/dev/null || true
gh label create "cli" --description "CLI commands" --color d4c5f9 2>/dev/null || true
gh label create "extension" --description "Chrome extension" --color bfd4f2 2>/dev/null || true
gh label create "documentation" --color 0075ca 2>/dev/null || true
gh label create "ux" --description "User experience" --color fbca04 2>/dev/null || true
```

---

#### Issue 1: Add `--verbose` flag to `linkedout status`

**Labels:** `good first issue`, `enhancement`, `cli`

```markdown
## Description
Currently `linkedout status` shows a one-line summary. Add a `--verbose` flag that shows expanded stats: per-table row counts, embedding model info, last operation timestamps, disk usage of `~/linkedout-data/`.

## Relevant files
- `backend/src/linkedout/cli.py` — status command implementation (find the `@click.command` for status)

## Acceptance criteria
- [ ] `linkedout status` (default) still shows the concise summary
- [ ] `linkedout status --verbose` shows expanded stats
- [ ] Verbose output includes: per-table counts, embedding model, last operation time
- [ ] Tests updated/added

## Getting started
1. Clone the repo and run `/linkedout-setup` (see [Getting Started](docs/getting-started.md))
2. Run `linkedout status` to see current output
3. Add the `--verbose` Click option and extended query logic
4. Run `pytest backend/tests/` to verify
```

---

#### Issue 2: Add shell completion for `linkedout` CLI

**Labels:** `good first issue`, `enhancement`, `cli`, `documentation`

```markdown
## Description
Click supports automatic shell completion generation. Add instructions for setting up bash/zsh/fish completion for the `linkedout` CLI.

## Relevant files
- `backend/src/linkedout/cli.py` — CLI entry point (Click group)
- `docs/configuration.md` — Add a section on shell completion

## Acceptance criteria
- [ ] `_LINKEDOUT_COMPLETE=bash_source linkedout` generates bash completion script
- [ ] `_LINKEDOUT_COMPLETE=zsh_source linkedout` generates zsh completion script
- [ ] Instructions added to `docs/configuration.md` for each shell
- [ ] Works for all 13 `linkedout` commands

## Getting started
1. See Click docs on [shell completion](https://click.palletsprojects.com/en/8.1.x/shell-completion/)
2. Test with your shell: `eval "$(_LINKEDOUT_COMPLETE=bash_source linkedout)"`
3. Add setup instructions to the configuration guide
```

---

#### Issue 3: Add `--format csv` to `linkedout diagnostics`

**Labels:** `good first issue`, `enhancement`, `cli`

```markdown
## Description
`linkedout diagnostics` currently supports `--json` and human-readable output. Add a `--format csv` option for users who want to import diagnostic data into spreadsheets.

## Relevant files
- `backend/src/linkedout/cli.py` — diagnostics command implementation

## Acceptance criteria
- [ ] `linkedout diagnostics --format csv` outputs valid CSV
- [ ] CSV includes all sections from the human-readable output
- [ ] Existing `--json` flag still works
- [ ] Tests updated/added

## Getting started
1. Run `linkedout diagnostics` and `linkedout diagnostics --json` to see current output
2. Add a `--format` Click option (choices: `text`, `json`, `csv`)
3. Use Python's `csv` module for output generation
```

---

#### Issue 4: Add connection import statistics to `linkedout status`

**Labels:** `good first issue`, `enhancement`, `cli`

```markdown
## Description
Show import history in `linkedout status`: last import date, total imports run, connections added in the last 30 days.

## Relevant files
- `backend/src/linkedout/cli.py` — status command
- `backend/src/linkedout/import_pipeline/` — import logic (for understanding what data is available)

## Acceptance criteria
- [ ] `linkedout status` shows: last import date, total import count, connections added in last 30 days
- [ ] Data comes from existing database tables (no new tables needed)
- [ ] Handles case where no imports have been run yet

## Getting started
1. Run `linkedout status` to see current output
2. Check the database schema for import-related timestamps
3. Add queries to pull import statistics
```

---

#### Issue 5: Improve error message when PostgreSQL is not running

**Labels:** `good first issue`, `enhancement`, `ux`

```markdown
## Description
When PostgreSQL isn't available, LinkedOut shows a raw connection error. Improve this to detect the specific failure and suggest a fix:
- PostgreSQL not installed → "Install PostgreSQL: `sudo apt install postgresql`"
- PostgreSQL not running → "Start PostgreSQL: `sudo systemctl start postgresql`"
- Wrong port/host → "Check DATABASE_URL in config.yaml"

## Relevant files
- `backend/src/shared/config/` — startup validation and connection handling

## Acceptance criteria
- [ ] User-friendly error message replaces raw traceback
- [ ] Message identifies the specific problem (not installed / not running / wrong config)
- [ ] Message suggests the fix
- [ ] Works on both Ubuntu and macOS

## Getting started
1. Stop PostgreSQL (`sudo systemctl stop postgresql`) and run any `linkedout` command
2. Observe the current error message
3. Add detection logic in the config/startup code
```

---

#### Issue 6: Add dark mode support to Chrome extension side panel

**Labels:** `good first issue`, `enhancement`, `extension`

```markdown
## Description
The Chrome extension side panel should respect `prefers-color-scheme: dark` for users who have dark mode enabled in their OS/browser.

## Relevant files
- `extension/entrypoints/sidepanel/` — Side panel HTML/CSS/JS

## Acceptance criteria
- [ ] Side panel respects `prefers-color-scheme: dark`
- [ ] Colors are readable in both light and dark mode
- [ ] No hard-coded colors that break in dark mode

## Getting started
1. Load the extension in Chrome (see [Extension Guide](docs/extension.md))
2. Enable dark mode in your OS settings
3. Add CSS `@media (prefers-color-scheme: dark)` rules
```

---

#### Issue 7: Add `man`-style examples to CLI commands

**Labels:** `good first issue`, `documentation`, `cli`

```markdown
## Description
Each `linkedout` command's `--help` should include 2-3 usage examples. Click supports this via the `epilog` parameter on commands.

## Relevant files
- `backend/src/linkedout/cli.py` — all CLI commands

## Acceptance criteria
- [ ] Every `linkedout` command includes examples in `--help` output
- [ ] Examples use realistic data (file paths, flags)
- [ ] Examples render cleanly in terminal (proper indentation)

## Getting started
1. Run `linkedout import-connections --help` to see current output
2. Add `epilog` parameter to each `@click.command()` with example usage
3. See Click docs on [command help](https://click.palletsprojects.com/en/8.1.x/documentation/)
```

---

#### Issue 8: Add config validation command

**Labels:** `good first issue`, `enhancement`, `cli`

```markdown
## Description
Add `linkedout config validate` — check `config.yaml` and `secrets.yaml` for common mistakes: invalid YAML, unknown keys, wrong types, missing required fields.

## Relevant files
- `backend/src/linkedout/cli.py` — CLI commands
- `backend/src/shared/config/` — configuration system (pydantic-settings)

## Acceptance criteria
- [ ] `linkedout config validate` checks both config files
- [ ] Reports: invalid YAML syntax, unknown config keys, wrong value types
- [ ] Exits 0 if valid, non-zero if problems found
- [ ] Human-readable output with specific fix suggestions

## Getting started
1. Look at the pydantic-settings model in `backend/src/shared/config/config.py`
2. Add a `config validate` Click command that loads and validates config
3. Test with intentionally broken config files
```

---

### Issue template format

Each issue above follows this structure:
```markdown
## Description
[What needs to be done]

## Relevant files
- `path/to/file.py` — [what this file does]

## Acceptance criteria
- [ ] [specific, testable criterion]

## Getting started
1. Clone the repo and run setup (see README)
2. [specific steps to reproduce/test]
3. Run `pytest tests/...` to verify
```

---

## Verification

- [ ] 8 issues created with `good first issue` label
- [ ] Each issue has: description, relevant files, acceptance criteria, getting started steps
- [ ] Issues span different areas: CLI (5), extension (1), docs (1), config (1)
- [ ] Issues are genuinely approachable (no deep domain knowledge required)
- [ ] No issue requires paid API keys to work on
- [ ] All file paths in issues are accurate (verify they exist in the codebase)

---

## Output Artifacts

- 8 GitHub issues created via `gh issue create`
- Each labeled with `good first issue` plus relevant area labels

---

## Post-Completion Check

1. All issues are visible on the repo's Issues tab
2. Labels are correctly applied
3. File paths referenced in issues actually exist in the codebase
4. No issues reference internal/private information

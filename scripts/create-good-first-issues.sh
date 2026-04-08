#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Creates "good first issue" GitHub issues for LinkedOut OSS.
# Prerequisites: gh auth login
set -euo pipefail

echo "=== Creating labels ==="
gh label create "good first issue" --description "Good for newcomers" --color 7057ff 2>/dev/null || echo "Label 'good first issue' already exists"
gh label create "enhancement" --color a2eeef 2>/dev/null || echo "Label 'enhancement' already exists"
gh label create "cli" --description "CLI commands" --color d4c5f9 2>/dev/null || echo "Label 'cli' already exists"
gh label create "extension" --description "Chrome extension" --color bfd4f2 2>/dev/null || echo "Label 'extension' already exists"
gh label create "documentation" --color 0075ca 2>/dev/null || echo "Label 'documentation' already exists"
gh label create "ux" --description "User experience" --color fbca04 2>/dev/null || echo "Label 'ux' already exists"

echo ""
echo "=== Creating issues ==="

# Issue 1
echo "Creating issue 1: Add --verbose flag to linkedout status..."
gh issue create \
  --label "good first issue" --label "enhancement" --label "cli" \
  --title "Add \`--verbose\` flag to \`linkedout status\`" \
  --body "$(cat <<'EOF'
## Description

Currently `linkedout status` shows a one-line summary. Add a `--verbose` flag that shows expanded stats: per-table row counts, embedding model info, last operation timestamps, disk usage of `~/linkedout-data/`.

## Relevant files

- `backend/src/linkedout/commands/status.py` — status command implementation
- `backend/src/linkedout/cli.py` — CLI entry point (registers all commands)

## Acceptance criteria

- [ ] `linkedout status` (default) still shows the concise summary
- [ ] `linkedout status --verbose` shows expanded stats
- [ ] Verbose output includes: per-table counts, embedding model, last operation time
- [ ] Tests updated/added

## Getting started

1. Clone the repo and follow the [Getting Started](docs/getting-started.md) guide
2. Run `linkedout status` to see current output
3. Add the `--verbose` Click option to `backend/src/linkedout/commands/status.py`
4. Run `pytest backend/tests/` to verify
EOF
)"

# Issue 2
echo "Creating issue 2: Add shell completion for linkedout CLI..."
gh issue create \
  --label "good first issue" --label "enhancement" --label "cli" --label "documentation" \
  --title "Add shell completion for \`linkedout\` CLI" \
  --body "$(cat <<'EOF'
## Description

Click supports automatic shell completion generation. Add instructions for setting up bash/zsh/fish completion for the `linkedout` CLI.

## Relevant files

- `backend/src/linkedout/cli.py` — CLI entry point (Click group)
- `docs/configuration.md` — Add a section on shell completion

## Acceptance criteria

- [ ] `_LINKEDOUT_COMPLETE=bash_source linkedout` generates bash completion script
- [ ] `_LINKEDOUT_COMPLETE=zsh_source linkedout` generates zsh completion script
- [ ] Instructions added to `docs/configuration.md` for each shell
- [ ] Works for all `linkedout` commands

## Getting started

1. See Click docs on [shell completion](https://click.palletsprojects.com/en/8.1.x/shell-completion/)
2. Test with your shell: `eval "$(_LINKEDOUT_COMPLETE=bash_source linkedout)"`
3. Add setup instructions to the configuration guide
EOF
)"

# Issue 3
echo "Creating issue 3: Add --format csv to linkedout diagnostics..."
gh issue create \
  --label "good first issue" --label "enhancement" --label "cli" \
  --title "Add \`--format csv\` to \`linkedout diagnostics\`" \
  --body "$(cat <<'EOF'
## Description

`linkedout diagnostics` currently supports `--json` and human-readable output. Add a `--format csv` option for users who want to import diagnostic data into spreadsheets.

## Relevant files

- `backend/src/linkedout/commands/diagnostics.py` — diagnostics command implementation

## Acceptance criteria

- [ ] `linkedout diagnostics --format csv` outputs valid CSV
- [ ] CSV includes all sections from the human-readable output
- [ ] Existing `--json` flag still works
- [ ] Tests updated/added

## Getting started

1. Run `linkedout diagnostics` and `linkedout diagnostics --json` to see current output
2. Add a `--format` Click option (choices: `text`, `json`, `csv`) to `backend/src/linkedout/commands/diagnostics.py`
3. Use Python's `csv` module for output generation
EOF
)"

# Issue 4
echo "Creating issue 4: Add connection import statistics to linkedout status..."
gh issue create \
  --label "good first issue" --label "enhancement" --label "cli" \
  --title "Add connection import statistics to \`linkedout status\`" \
  --body "$(cat <<'EOF'
## Description

Show import history in `linkedout status`: last import date, total imports run, connections added in the last 30 days.

## Relevant files

- `backend/src/linkedout/commands/status.py` — status command
- `backend/src/linkedout/import_pipeline/` — import logic (for understanding what data is available)

## Acceptance criteria

- [ ] `linkedout status` shows: last import date, total import count, connections added in last 30 days
- [ ] Data comes from existing database tables (no new tables needed)
- [ ] Handles case where no imports have been run yet

## Getting started

1. Run `linkedout status` to see current output
2. Check the database schema for import-related timestamps
3. Add queries to `backend/src/linkedout/commands/status.py` to pull import statistics
EOF
)"

# Issue 5
echo "Creating issue 5: Improve error message when PostgreSQL is not running..."
gh issue create \
  --label "good first issue" --label "enhancement" --label "ux" \
  --title "Improve error message when PostgreSQL is not running" \
  --body "$(cat <<'EOF'
## Description

When PostgreSQL isn't available, LinkedOut shows a raw connection error. Improve this to detect the specific failure and suggest a fix:
- PostgreSQL not installed → "Install PostgreSQL: `sudo apt install postgresql`"
- PostgreSQL not running → "Start PostgreSQL: `sudo systemctl start postgresql`"
- Wrong port/host → "Check DATABASE_URL in config.yaml"

## Relevant files

- `backend/src/shared/config/` — startup validation and connection handling
- `backend/src/shared/config/config.py` — configuration singleton

## Acceptance criteria

- [ ] User-friendly error message replaces raw traceback
- [ ] Message identifies the specific problem (not installed / not running / wrong config)
- [ ] Message suggests the fix
- [ ] Works on both Ubuntu and macOS

## Getting started

1. Stop PostgreSQL (`sudo systemctl stop postgresql`) and run any `linkedout` command
2. Observe the current error message
3. Add detection logic in `backend/src/shared/config/`
EOF
)"

# Issue 6
echo "Creating issue 6: Add dark mode support to Chrome extension side panel..."
gh issue create \
  --label "good first issue" --label "enhancement" --label "extension" \
  --title "Add dark mode support to Chrome extension side panel" \
  --body "$(cat <<'EOF'
## Description

The Chrome extension side panel should respect `prefers-color-scheme: dark` for users who have dark mode enabled in their OS/browser.

## Relevant files

- `extension/entrypoints/sidepanel/` — Side panel HTML/CSS/JS (React + TypeScript)
- `extension/entrypoints/sidepanel/App.tsx` — Main app component
- `extension/entrypoints/sidepanel/index.html` — HTML entry point

## Acceptance criteria

- [ ] Side panel respects `prefers-color-scheme: dark`
- [ ] Colors are readable in both light and dark mode
- [ ] No hard-coded colors that break in dark mode

## Getting started

1. Load the extension in Chrome (see [Extension Guide](docs/extension.md))
2. Enable dark mode in your OS settings
3. Add CSS `@media (prefers-color-scheme: dark)` rules
EOF
)"

# Issue 7
echo "Creating issue 7: Add man-style examples to CLI commands..."
gh issue create \
  --label "good first issue" --label "documentation" --label "cli" \
  --title "Add man-style usage examples to CLI command help text" \
  --body "$(cat <<'EOF'
## Description

Each `linkedout` command's `--help` should include 2-3 usage examples. Click supports this via the `epilog` parameter on commands.

## Relevant files

- `backend/src/linkedout/commands/` — all CLI command files (one per command)
- `backend/src/linkedout/cli.py` — CLI entry point

## Acceptance criteria

- [ ] Every `linkedout` command includes examples in `--help` output
- [ ] Examples use realistic data (file paths, flags)
- [ ] Examples render cleanly in terminal (proper indentation)

## Getting started

1. Run `linkedout import-connections --help` to see current output
2. Add `epilog` parameter to each `@click.command()` in files under `backend/src/linkedout/commands/`
3. See Click docs on [command help](https://click.palletsprojects.com/en/8.1.x/documentation/)
EOF
)"

# Issue 8
echo "Creating issue 8: Add config validation command..."
gh issue create \
  --label "good first issue" --label "enhancement" --label "cli" \
  --title "Add \`linkedout config validate\` command" \
  --body "$(cat <<'EOF'
## Description

Add `linkedout config validate` — check `config.yaml` and `secrets.yaml` for common mistakes: invalid YAML, unknown keys, wrong types, missing required fields.

## Relevant files

- `backend/src/linkedout/commands/config.py` — existing `config` command group
- `backend/src/shared/config/config.py` — configuration system (pydantic-settings model)

## Acceptance criteria

- [ ] `linkedout config validate` checks both config files
- [ ] Reports: invalid YAML syntax, unknown config keys, wrong value types
- [ ] Exits 0 if valid, non-zero if problems found
- [ ] Human-readable output with specific fix suggestions

## Getting started

1. Look at the pydantic-settings model in `backend/src/shared/config/config.py`
2. Add a `validate` subcommand to the existing config group in `backend/src/linkedout/commands/config.py`
3. Test with intentionally broken config files
EOF
)"

echo ""
echo "=== Done ==="
echo "Created 8 good first issues. Run 'gh issue list --label \"good first issue\"' to verify."

# Contributing to LinkedOut

Thanks for your interest in contributing to LinkedOut! This guide covers everything you need to get started.

## Development Setup

### Clone and install

```bash
git clone https://github.com/sridherj/linkedout-oss.git
cd linkedout-oss
```

### Install dependencies

LinkedOut uses `uv` for Python dependency management.

```bash
pip install uv
cd backend
uv pip install -r requirements.txt
uv pip install -e .
```

Once dev dependencies are available:

```bash
uv pip install -r backend/requirements-dev.txt
```

### PostgreSQL

You need a local PostgreSQL instance with the `pgvector` extension. Create a database for LinkedOut and ensure `pgvector` is enabled:

```sql
CREATE DATABASE linkedout;
\c linkedout
CREATE EXTENSION IF NOT EXISTS vector;
```

For detailed setup (connection config, data directory, seed data), use the `/linkedout-setup` skill in Claude Code.

## Code Style

- **Formatter/linter:** [ruff](https://docs.astral.sh/ruff/) — configured in `pyproject.toml`
- **Type checker:** [pyright](https://github.com/microsoft/pyright) — configured in `pyproject.toml`
- **Line length:** 100 characters
- **Quote style:** Single quotes

Run checks locally:

```bash
cd backend
ruff check src/
ruff format --check src/
pyright src/
```

Pre-commit hooks are planned for a future phase. For now, run checks manually before pushing.

## Branch Naming

Use a prefix that describes the type of change:

- `feat/` — new feature (e.g., `feat/import-contacts-icloud`)
- `fix/` — bug fix (e.g., `fix/csv-encoding-error`)
- `docs/` — documentation (e.g., `docs/update-readme`)
- `refactor/` — code restructuring (e.g., `refactor/affinity-scoring`)

## PR Process

1. Fork the repository
2. Create a branch from `main` using the naming convention above
3. Make your changes
4. Ensure all checks pass (ruff, pyright, tests)
5. Open a PR against `main`
6. Fill in the PR template checklist (see `.github/PULL_REQUEST_TEMPLATE.md`)
7. All CI checks must pass
8. One approving review required

## Testing

### Test tools

- **Backend:** [pytest](https://docs.pytest.org/)
- **Extension:** [vitest](https://vitest.dev/)

### Running tests

```bash
cd backend
pytest tests/ -x
```

### Test requirements

- Tests must pass **without external API keys** — mock all LLM and external API calls
- Integration tests run against a real PostgreSQL database (not SQLite stubs)
- Three test tiers:
  1. **Static analysis** — ruff + pyright (fast, every commit)
  2. **Integration** — pytest against real PostgreSQL (every PR)
  3. **Installation** — end-to-end install + smoke test (nightly)

### Running lints

```bash
cd backend
ruff check src/
ruff format --check src/
pyright src/
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add iCloud contacts import
fix: handle UTF-8 BOM in LinkedIn CSV
docs: update CLI command table in README
refactor: extract affinity scoring into service
test: add integration tests for import pipeline
chore: update ruff to 0.4.x
```

Scope is optional but encouraged:

```
feat(import): add iCloud contacts support
fix(embed): handle empty profile text gracefully
```

## Project Structure

```
backend/src/
|-- linkedout/       Core domain logic
|-- shared/          Shared utilities (logger, config, models)
\-- dev_tools/       Development tooling

extension/           Chrome extension (WXT framework)
skills/              Cross-platform AI skill definitions
```

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

## Decision Documents

Architectural decisions are recorded in `docs/decision/`. Each document captures context, the decision, rationale, and constraints.

When proposing changes that affect architecture, check existing decisions first. New decisions follow the same format.

## Engineering Principles

See the [`/linkedout-dev` skill](skills/linkedout-dev/SKILL.md) for detailed engineering standards covering error handling, idempotency, logging, CLI design, configuration, and testing.

## Getting Help

- **Bug reports:** [GitHub Issues](https://github.com/sridherj/linkedout-oss/issues)
- **Questions and discussion:** [GitHub Discussions](https://github.com/sridherj/linkedout-oss/discussions)

# SP4: GitHub Infrastructure (Templates + CI)

**Phase:** 01 — OSS Repository Scaffolding
**Sub-phase:** 4 of 5
**Dependencies:** SP2 (README, CONTRIBUTING must exist for cross-references), SP3 (engineering principles for CI context)
**Estimated effort:** ~60 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Create GitHub issue templates, PR template, and CI workflow. These establish the contributor experience and quality gates.

**Tasks from phase plan:** 1H, 1H-b, 1I

---

## Required Reading Before Starting

1. `docs/decision/cli-surface.md` — `linkedout diagnostics` and `linkedout version` commands referenced in templates
2. Phase plan (`docs/plan/phase-01-oss-scaffolding.md`) — Resolved decisions Q3-Q5 about CI scope

---

## Task 1H: GitHub Issue Templates

**Files to create:**
- `.github/ISSUE_TEMPLATE/bug-report.yml`
- `.github/ISSUE_TEMPLATE/feature-request.yml`
- `.github/ISSUE_TEMPLATE/config.yml`

### Bug Report Template (`.github/ISSUE_TEMPLATE/bug-report.yml`)

YAML form format with fields:

```yaml
name: Bug Report
description: Report a bug in LinkedOut
title: "[Bug]: "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to report a bug! Please fill out the form below.
  - type: textarea
    id: description
    attributes:
      label: Description
      description: A clear description of the bug
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the behavior
      placeholder: |
        1. Run `linkedout import-connections ...`
        2. ...
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What you expected to happen
    validations:
      required: true
  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior
      description: What actually happened
    validations:
      required: true
  - type: textarea
    id: diagnostics
    attributes:
      label: Diagnostic Report
      description: "Paste the output of `linkedout diagnostics`"
      render: json
    validations:
      required: false
  - type: dropdown
    id: os
    attributes:
      label: Operating System
      options:
        - Linux (Debian/Ubuntu)
        - Linux (Arch)
        - Linux (Fedora/RPM)
        - macOS
        - Windows (WSL)
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: LinkedOut Version
      description: "Output of `linkedout version`"
      placeholder: "v0.1.0"
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: Additional Context
      description: Any other context about the problem
    validations:
      required: false
```

### Feature Request Template (`.github/ISSUE_TEMPLATE/feature-request.yml`)

```yaml
name: Feature Request
description: Suggest a new feature for LinkedOut
title: "[Feature]: "
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem Description
      description: What problem does this solve?
    validations:
      required: true
  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How would you like this to work?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: Any alternatives you've considered
    validations:
      required: false
  - type: textarea
    id: context
    attributes:
      label: Additional Context
      description: Any other context or screenshots
    validations:
      required: false
```

### Config Template (`.github/ISSUE_TEMPLATE/config.yml`)

```yaml
blank_issues_enabled: false
contact_links:
  - name: Questions & Discussion
    url: https://github.com/sridherj/linkedout-oss/discussions
    about: Ask questions and discuss LinkedOut
```

### Verification
- [ ] Bug report YAML is valid and has all 8 fields
- [ ] Feature request YAML is valid and has all 4 fields
- [ ] Config disables blank issues
- [ ] Config links to `sridherj/linkedout-oss` discussions
- [ ] `linkedout diagnostics` referenced in bug report template
- [ ] `linkedout version` referenced in bug report template

---

## Task 1H-b: Pull Request Template

**File to create:** `.github/PULL_REQUEST_TEMPLATE.md`

### Content

```markdown
## Summary
<!-- What does this PR do and why? -->

## Test Plan
<!-- How did you verify the changes? -->
- [ ] Tests pass (`cd backend && pytest tests/ -x`)
- [ ] Lint passes (`cd backend && ruff check src/`)
- [ ] Types pass (`cd backend && pyright src/`)

## Checklist
- [ ] SPDX headers on new files
- [ ] No secrets or hardcoded paths
- [ ] CHANGELOG.md updated (if user-facing)
```

### Verification
- [ ] File at correct path: `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] Has Summary, Test Plan, and Checklist sections
- [ ] Test commands match what's in CONTRIBUTING.md

---

## Task 1I: GitHub Actions CI

**File to create:** `.github/workflows/ci.yml`

### IMPORTANT: Phase 1 CI is lint + typecheck ONLY

Per resolved decisions Q4 and Q5:
- **Backend pytest:** Deferred to Phase 6 (depends on Procrastinate table removal)
- **Extension vitest:** Deferred to Phase 12 (extension not touched until then)

### Workflow

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install uv
          cd backend
          uv pip install --system -r requirements.txt
          uv pip install --system -e .
      - name: Ruff lint
        run: cd backend && ruff check src/
      - name: Ruff format check
        run: cd backend && ruff format --check src/

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install uv
          cd backend
          uv pip install --system -r requirements.txt
          uv pip install --system -e .
      - name: Pyright
        run: cd backend && pyright src/
```

### Key Design Decisions
- Python 3.12 only (matrix expansion deferred to Phase 13 — resolved decision Q3)
- Uses `uv` for dependency installation (project convention)
- `uv pip install --system` because GitHub Actions doesn't use venvs by default
- Two separate jobs (`lint`, `typecheck`) so failures are granular
- No backend tests (Phase 6) or extension tests (Phase 12)
- No external API keys needed

### Verification
- [ ] Workflow file is valid YAML
- [ ] Triggers on push to main and PRs against main
- [ ] Uses Python 3.12
- [ ] Uses `uv` for dependency installation
- [ ] `lint` job runs `ruff check` and `ruff format --check`
- [ ] `typecheck` job runs `pyright`
- [ ] No pytest or vitest jobs (deferred)
- [ ] No external API keys required

---

## Output Artifacts

- `.github/ISSUE_TEMPLATE/bug-report.yml`
- `.github/ISSUE_TEMPLATE/feature-request.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/ci.yml`

---

## Post-Completion Check

1. All YAML files are valid
2. No references to private repos, Docker, or internal tools
3. All GitHub URLs reference `sridherj/linkedout-oss`
4. CI workflow only has lint + typecheck (no test jobs yet)
5. Issue templates reference correct CLI commands (`linkedout diagnostics`, `linkedout version`)

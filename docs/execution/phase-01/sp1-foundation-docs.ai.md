# SP1: Foundation Documents

**Phase:** 01 — OSS Repository Scaffolding
**Sub-phase:** 1 of 5
**Dependencies:** None (first sub-phase)
**Estimated effort:** ~45 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Create the foundational repo-level files that don't depend on other files. These are independent of each other and establish the legal and hygiene baseline for the project.

**Tasks from phase plan:** 1A, 1D, 1E, 1F, 1G

---

## Task 1A: LICENSE + NOTICE

**Files to create:** `LICENSE`, `NOTICE` (repo root)

### LICENSE
- Standard Apache 2.0 license text from https://www.apache.org/licenses/LICENSE-2.0.txt
- Full, unmodified text

### NOTICE
```
LinkedOut OSS
Copyright 2026 Sridher Jeyachandran

Licensed under the Apache License, Version 2.0.
```

### Verification
- [ ] `LICENSE` contains the full Apache 2.0 text
- [ ] `NOTICE` contains project name, copyright year 2026, author "Sridher Jeyachandran"

---

## Task 1D: CODE_OF_CONDUCT.md

**File to create:** `CODE_OF_CONDUCT.md` (repo root)

### Content
- Full Contributor Covenant v2.1 text (https://www.contributor-covenant.org/version/2/1/code_of_conduct/)
- **Contact method:** GitHub Security Advisories (NOT email — resolved decision Q2)
- **Enforcement:** Project maintainers

### Verification
- [ ] Full Contributor Covenant v2.1 text present
- [ ] Contact method is GitHub Security Advisories (no email address)

---

## Task 1E: SECURITY.md

**File to create:** `SECURITY.md` (repo root)

### Sections
1. **Supported versions** — Table: v0.1.x receives security updates
2. **Reporting a vulnerability** — Use GitHub Security Advisories (private by default). Do NOT file public issues for security bugs.
3. **Response SLA** — Acknowledge within 72 hours, patch within 30 days for critical
4. **Scope** — What counts as a security issue (DB credential exposure, data leaks, injection) vs. what doesn't (local-only tool where user is the only operator)
5. **Security considerations** — LinkedOut is local-first; threat model assumes user trusts their own machine. API keys stored in `~/linkedout-data/config/secrets.yaml` with `chmod 600`.

### Key references
- Data directory: `~/linkedout-data/` (from `docs/decision/env-config-design.md`)
- Secrets file: `~/linkedout-data/config/secrets.yaml` with `chmod 600`

### Verification
- [ ] Vulnerability reporting process is clear
- [ ] GitHub Security Advisories referenced (not email)
- [ ] Threat model acknowledges local-first architecture
- [ ] References `~/linkedout-data/config/secrets.yaml` for API key storage

---

## Task 1F: CHANGELOG.md

**File to create:** `CHANGELOG.md` (repo root)

### Content
Follow Keep a Changelog format (https://keepachangelog.com/en/1.1.0/):

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial open-source repository scaffolding
- Apache 2.0 license
- Contributing guide, code of conduct, security policy
- GitHub Actions CI (lint, type check)
- GitHub issue and PR templates
```

### Verification
- [ ] Follows Keep a Changelog format exactly
- [ ] Has `[Unreleased]` section with initial entries
- [ ] No version numbers yet (all unreleased)

---

## Task 1G: .gitignore Overhaul

**File to modify:** `.gitignore` (repo root — currently contains only `.taskos`)

### IMPORTANT: Check `backend/.gitignore` first
Read `backend/.gitignore` before writing the root `.gitignore` to avoid duplicating patterns. The root `.gitignore` handles repo-wide patterns; `backend/.gitignore` handles backend-specific patterns.

### Categories to add

1. **Environment & secrets:**
   ```
   .env
   .env.*
   !.env.example
   secrets.yaml
   *.secret
   *.key
   ```

2. **Python:**
   ```
   __pycache__/
   *.py[cod]
   *$py.class
   *.egg-info/
   dist/
   build/
   .eggs/
   *.egg
   .venv/
   venv/
   ```

3. **Node/TypeScript (extension):**
   ```
   node_modules/
   .output/
   .wxt/
   ```

4. **Data files:**
   ```
   *.sqlite
   *.sqlite3
   *.db
   ```

5. **IDE configs:**
   ```
   .idea/
   .vscode/
   *.swp
   *.swo
   *~
   .DS_Store
   ```

6. **Logs & reports:**
   ```
   *.log
   logs/
   ```

7. **Testing:**
   ```
   .pytest_cache/
   .coverage
   htmlcov/
   .mypy_cache/
   ```

8. **LinkedOut specific:**
   ```
   .taskos
   ```

### Constraints
- Keep `.taskos` entry (already present)
- Don't add `~/linkedout-data/` to .gitignore (it's outside the repo by design)
- Check `backend/.gitignore` for conflicts before writing

### Verification
- [ ] `.env*` files blocked (except `.env.example`)
- [ ] `__pycache__/`, `node_modules/`, IDE configs, sqlite files blocked
- [ ] `.taskos` still ignored
- [ ] No conflicts with `backend/.gitignore`
- [ ] Organized with clear section headers/comments

---

## Output Artifacts

All files created in the repo root:
- `LICENSE`
- `NOTICE`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `CHANGELOG.md`
- `.gitignore` (modified)

---

## Post-Completion Check

After all files are created, verify:
1. No references to private repos, Docker, internal tools, or email addresses
2. All file names are exactly as specified (case-sensitive)
3. `.gitignore` doesn't conflict with `backend/.gitignore`

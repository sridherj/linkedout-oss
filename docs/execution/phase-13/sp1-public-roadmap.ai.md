# SP1: Public Roadmap

**Phase:** 13 — Polish & Launch
**Sub-phase:** 1 of 6
**Dependencies:** None (first sub-phase, no dependencies)
**Estimated effort:** ~30 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Create a public roadmap so contributors and users know where the project is headed. This includes a GitHub Projects board and a `ROADMAP.md` file in the repo root.

**Tasks from phase plan:** 13G

---

## Task 13G: Public Roadmap

### Part 1: ROADMAP.md

**File to create:** `ROADMAP.md` (repo root)

Write a text-based roadmap that summarizes the project's direction. This is a static file that doesn't depend on GitHub Projects — it's the fallback for users who don't use GitHub's project boards.

#### Sections

1. **Current Release (v0.1.0)** — Brief summary of what's shipped:
   - AI-native professional network intelligence via Claude Code / Codex / Copilot skills
   - 13 CLI commands under `linkedout` namespace
   - Local-first: all data in `~/linkedout-data/`
   - Dual embedding: OpenAI (fast) or nomic-embed-text-v1.5 (free, local)
   - Optional Chrome extension for LinkedIn profile crawling
   - Comprehensive diagnostics and readiness reporting

2. **Up Next** — Prioritized for next release:
   - Chrome Web Store listing (extension distribution)
   - `linkedout export` — Export network data (CSV, JSON)
   - `linkedout backup` — Backup `~/linkedout-data/`
   - Cloud-hosted shared database option
   - `linkedout enrich-profiles` — Local enrichment pipeline

3. **Future** — Longer-term ideas:
   - Web dashboard (read-only network visualization)
   - Multi-user / team features
   - Additional AI platform support (beyond Claude Code / Codex / Copilot)
   - Mobile companion app
   - Paid/hosted tier

4. **Community Requests** — Brief note: "Have an idea? Open an issue with the `feature-request` label."

#### Constraints
- No references to Docker, web frontend as current feature, or internal tools
- Use `linkedout` flat namespace for any CLI command references
- Data directory is `~/linkedout-data/` everywhere

### Part 2: GitHub Projects Board

**Create via `gh` CLI commands:**

1. Create a new GitHub Project (Kanban board):
   ```bash
   gh project create --owner sridherj --title "LinkedOut OSS Roadmap" --format board
   ```

2. Add columns: **Done**, **Up Next**, **Future**, **Community Requests**

3. Populate with items matching the ROADMAP.md content above

4. Link the project from the repo settings or README

**Note:** If `gh project` commands require specific auth scopes or fail, document the manual steps in a comment and create the board manually. The `ROADMAP.md` file is the primary deliverable; the GitHub Projects board is a nice-to-have.

### Part 3: README.md Updates

**File to modify:** `README.md`

Add a "Roadmap" section (or link in existing navigation) that points to:
- `ROADMAP.md` for the text summary
- The GitHub Projects board URL (once created)

---

## Verification

- [ ] `ROADMAP.md` exists in repo root with all four sections
- [ ] At least 10 items across roadmap categories
- [ ] README.md links to `ROADMAP.md`
- [ ] No references to Docker, internal tools, or private repos
- [ ] All CLI references use `linkedout` flat namespace
- [ ] Data directory is `~/linkedout-data/`
- [ ] If GitHub Projects board was created: it's public and linked from README

---

## Output Artifacts

- `ROADMAP.md` (repo root — new)
- `README.md` (repo root — modified, add roadmap link)
- GitHub Projects board (if feasible via CLI)

---

## Post-Completion Check

1. No references to private repos, Docker, internal tools, or email addresses
2. `ROADMAP.md` renders correctly in GitHub markdown
3. README link to roadmap is not broken

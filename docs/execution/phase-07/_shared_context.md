# Phase 07: Seed Data Pipeline — Shared Context

**Project:** LinkedOut OSS
**Phase:** 7 — Seed Data Pipeline
**Phase Plan:** `docs/plan/phase-07-seed-data.md`
**Status:** Ready for implementation

---

## Project Overview

LinkedOut is a self-hosted, AI-native professional network intelligence tool. The user imports LinkedIn connections, enriches profiles, generates embeddings, and queries their network through CLI commands and a Chrome extension. The primary interface is a Claude Code / Codex / Copilot skill, with CLI commands as the underlying building blocks.

This phase delivers a seed data pipeline so users get a useful company database without needing Apify enrichment. A fresh install can run `linkedout download-seed && linkedout import-seed` and have a populated company database.

---

## Architecture Decisions (Binding Constraints)

### CLI Surface
- **Decision doc:** `docs/decision/cli-surface.md`
- `linkedout download-seed` and `linkedout import-seed` are the user-facing commands
- Flat namespace, no subgroups
- Both follow the Operation Result Pattern: Progress → Summary → Gaps → Next steps → Report path

### Data Directory
- **Decision doc:** `docs/decision/2026-04-07-data-directory-convention.md`
- Seed files download to `~/linkedout-data/seed/`
- Config via `LINKEDOUT_DATA_DIR` override
- No separate `~/.linkedout/` directory

### Logging
- **Decision doc:** `docs/decision/logging-observability-strategy.md`
- Both commands log to `~/linkedout-data/logs/cli.log` using loguru via `get_logger()`
- Each produces a readiness report to `~/linkedout-data/reports/`
- Human-readable log format (no JSON logs)

### Queue Strategy
- **Decision doc:** `docs/decision/queue-strategy.md`
- No Procrastinate. Import runs synchronously.

### Embeddings
- **Decision doc:** `docs/decision/2026-04-07-embedding-model-selection.md`
- Seed data does NOT include embeddings — embeddings are generated locally after import via `linkedout embed`
- Seed profiles ship raw text only

---

## Seed Data Scope

### Included Tables (10 tables, not tenant-scoped)

| Table | Entity | Notes |
|-------|--------|-------|
| `company` | `CompanyEntity` | Company reference data |
| `company_alias` | `CompanyAliasEntity` | Company name variations |
| `role_alias` | `RoleAliasEntity` | Job title normalization |
| `funding_round` | `FundingRoundEntity` | Public funding data |
| `startup_tracking` | `StartupTrackingEntity` | Startup metrics |
| `growth_signal` | `GrowthSignalEntity` | Growth indicators |
| `crawled_profile` | `CrawledProfileEntity` | Profile snapshots |
| `experience` | `ExperienceEntity` | Work history |
| `education` | `EducationEntity` | Education history |
| `profile_skill` | `ProfileSkillEntity` | Skills/endorsements |

### Excluded (tenant/BU/user-scoped)
- `connection`, `contact_source`, `enrichment_event`, `import_job`
- `search_session`, `search_turn`, `search_tag`

### Two Tiers
- **Core (~50MB):** ~5K companies (where SJ's real connections work) + full profile/role/funding data
- **Full (~500MB):** ~50-100K companies (top global companies by employee count, funding, web traffic) + same profile data

---

## Key Files & Paths

### Entity Files (Read-Only Reference)
| File | Entity |
|------|--------|
| `backend/src/linkedout/company/entities/company_entity.py` | `CompanyEntity` |
| `backend/src/linkedout/company_alias/entities/company_alias_entity.py` | `CompanyAliasEntity` |
| `backend/src/linkedout/role_alias/entities/role_alias_entity.py` | `RoleAliasEntity` |
| `backend/src/linkedout/funding/entities/funding_round_entity.py` | `FundingRoundEntity` |
| `backend/src/linkedout/funding/entities/startup_tracking_entity.py` | `StartupTrackingEntity` |
| `backend/src/linkedout/funding/entities/growth_signal_entity.py` | `GrowthSignalEntity` |
| `backend/src/linkedout/crawled_profile/entities/crawled_profile_entity.py` | `CrawledProfileEntity` |
| `backend/src/linkedout/experience/entities/experience_entity.py` | `ExperienceEntity` |
| `backend/src/linkedout/education/entities/education_entity.py` | `EducationEntity` |
| `backend/src/linkedout/profile_skill/entities/profile_skill_entity.py` | `ProfileSkillEntity` |

### Infrastructure Files
| File | Description |
|------|-------------|
| `backend/src/shared/infra/db/db_session_manager.py` | DB session management |
| `backend/src/linkedout/cli/cli.py` | CLI entry point (register new commands here) |

### New Files (Created by Sub-Phases)
| File | Sub-Phase | Description |
|------|-----------|-------------|
| `backend/src/dev_tools/seed_export.py` | SP2 | Maintainer curation script (PostgreSQL → SQLite + manifest) |
| `backend/src/linkedout/cli/commands/download_seed.py` | SP3 | `linkedout download-seed` command |
| `backend/src/linkedout/cli/commands/import_seed.py` | SP4 | `linkedout import-seed` command |
| `seed-data/README.md` | SP1 | Seed data documentation |
| `seed-data/.gitkeep` | SP1 | Directory placeholder |
| `backend/tests/unit/cli/test_download_seed.py` | SP6 | Download command unit tests |
| `backend/tests/unit/cli/test_import_seed.py` | SP6 | Import command unit tests |
| `backend/tests/integration/cli/test_seed_pipeline.py` | SP6 | Integration tests |
| `backend/tests/fixtures/test-seed-core.sqlite` | SP6 | Test fixture |

### Modified Files
| File | Sub-Phase | Changes |
|------|-----------|---------|
| `backend/src/linkedout/cli/cli.py` | SP3, SP4 | Register `download-seed` and `import-seed` commands |
| `.gitignore` | SP1 | Add `seed-data/*.sqlite`, `seed-data/*.db` |
| `backend/requirements.txt` | SP3 | Add `tqdm` if not present |

---

## Import Order (FK Constraints)

When importing seed data into PostgreSQL, tables must be imported in this order:

1. `company` (no FK dependencies)
2. `company_alias` (FK → company)
3. `role_alias` (no FK)
4. `funding_round` (FK → company)
5. `startup_tracking` (FK → company)
6. `growth_signal` (FK → company)
7. `crawled_profile` (FK → company via current_company_id, nullable)
8. `experience` (FK → crawled_profile, FK → company)
9. `education` (FK → crawled_profile)
10. `profile_skill` (FK → crawled_profile)

---

## Open Questions (Resolved)

1. **GitHub Release URL:** Hardcode `https://github.com/sridherj/linkedout-oss/releases/download/<version>/` with `LINKEDOUT_SEED_URL` env var override for forks.
2. **Seed format:** SQLite (portable, inspectable, single file).
3. **Profile PII:** Strip email, phone, internal notes. Keep names, LinkedIn URLs, headlines, summaries, photo URLs.
4. **CI testing:** Use small test fixture. Nightly/release tests with real seed files.
5. **Company dedup:** Already handled by import pipeline's company matching logic — no extra work needed.
6. **Embeddings:** NOT included in seed data. Users run `linkedout embed` after import.

---

## Sub-Phase Dependency Graph

```
SP1 (directory structure + manifest schema + docs)
 ├──→ SP2 (seed export curation script)
 │     └──→ SP5 (GitHub Release publishing docs)
 ├──→ SP3 (download-seed CLI command)
 ├──→ SP4 (import-seed CLI command)
 └──→ SP6 (integration testing) [requires SP3 + SP4]
```

**Parallelizable:** SP2, SP3, SP4 can all run in parallel after SP1.
**Sequential:** SP5 requires SP2. SP6 requires SP3 + SP4.

---

## Testing Approach

### Layer 1: Unit Tests (CI, no external deps)
- SQLite parsing and row extraction
- Checksum computation and verification
- Manifest parsing and validation
- FK ordering logic
- Upsert conflict resolution logic
- Operation Result output formatting

### Layer 2: Integration Tests (CI, require test PostgreSQL)
- Full import pipeline: test SQLite → PostgreSQL with real schema
- Idempotency: import twice, verify counts
- FK constraint validation: correct ordering imports cleanly
- Dry-run mode: verify no writes
- Report generation: verify JSON report structure

### Layer 3: Manual/Nightly (not in regular CI)
- Full-size seed file import (50MB core)
- Download from real GitHub Release URL
- Performance benchmarking

---

## What NOT to Do

- Do NOT include embeddings in seed data
- Do NOT include tenant-scoped tables (connection, contact_source, etc.)
- Do NOT use pg_dump — use SQLite for portability
- Do NOT add new pip dependencies beyond tqdm (for progress bars)
- Do NOT put seed SQLite files in git — they go in GitHub Releases
- Do NOT change the CLI namespace (it's `linkedout`, established in Phase 6)
- Do NOT add async/queue-based import — it runs synchronously

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When writing `seed_export.py`, `download_seed.py`, `import_seed.py` |
| `.claude/skills/pytest-best-practices/SKILL.md` | When writing tests (SP6) — naming, AAA pattern, fixtures |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating new CLI command modules |

### Agents (sub-phase specific)
| Agent | Sub-Phase | When to Invoke |
|-------|-----------|---------------|
| `.claude/agents/seed-db-creator-agent.md` | SP2 (export curation) | Reference for seeding infrastructure patterns — `SeedConfig`, `BaseSeeder`, `ENTITY_ORDER`, `EntityFactory` |
| `.claude/agents/seed-test-db-creator-agent.md` | SP6 (integration tests) | Reference for test seeding patterns — `SeedDb`, `TableName` enum, deterministic IDs |
| `.claude/agents/integration-test-creator-agent.md` | SP6 (integration tests) | Reference for integration test fixtures, session-scoped DB setup, test data patterns |

### Notes
- The seed agents are highly relevant — Phase 7 builds the user-facing seed pipeline, and these agents encode the existing test seeding conventions
- Ensure import order (FK constraints table above) aligns with `ENTITY_ORDER` in the existing seeding infrastructure

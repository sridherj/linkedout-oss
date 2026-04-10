# Phase 04: Constants Externalization — Shared Context

**Phase:** 4 of 13
**Dependencies:** Phase 2 (Environment & Configuration System), Phase 3 (Logging & Observability)
**Delivers:** Every hardcoded magic number, URL, threshold, model name, and ID in both backend and extension is externalized to config with a sensible default.

---

## Project Architecture

LinkedOut OSS is a self-installable, AI-native professional network intelligence tool. Two codebases:

- **Backend (Python):** FastAPI + SQLAlchemy + PostgreSQL + pydantic-settings. Entry point: `backend/main.py`. Config: `backend/src/shared/config/config.py` using `LinkedOutSettings(BaseSettings)`.
- **Extension (TypeScript):** Chrome extension built with WXT. Constants in `extension/lib/constants.ts`. Config target: `extension/lib/config.ts` with `browser.storage.local` fallbacks.

---

## Config System (Built in Phase 2)

Three-layer hierarchy (env vars > YAML > defaults):

1. **Environment variables** — `LINKEDOUT_` prefix for LinkedOut-specific, industry-standard names kept as-is (`DATABASE_URL`, `OPENAI_API_KEY`)
2. **`~/linkedout-data/config/config.yaml`** — human-readable YAML
3. **`~/linkedout-data/config/secrets.yaml`** — API keys, `chmod 600`
4. **Code defaults** — in `LinkedOutSettings` pydantic-settings class

YAML-to-env mapping: `snake_case` YAML key → `LINKEDOUT_UPPER_SNAKE_CASE` env var.

For nested config (e.g., scoring), use nested pydantic models. Env var override: `LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP=0.35` (double underscore for nesting).

Reference: `docs/decision/env-config-design.md`

---

## Key Decision Documents

These documents contain approved decisions that MUST be followed:

| Document | Key Decisions for Phase 4 |
|----------|--------------------------|
| `docs/decision/env-config-design.md` | Three-layer config hierarchy, `LINKEDOUT_` prefix, pydantic-settings implementation, `LinkedOutSettings` class structure |
| `docs/decision/cli-surface.md` | `linkedout config show` displays all config (secrets redacted). No new CLI commands needed for Phase 4 |
| `docs/decision/logging-observability-strategy.md` | Log rotation 50 MB, retention 30 days. Config vars: `LINKEDOUT_LOG_ROTATION`, `LINKEDOUT_LOG_RETENTION` |
| `docs/decision/queue-strategy.md` | Procrastinate removed. Enrichment runs synchronously. Enrichment timeouts/retry config externalized here |
| `docs/decision/2026-04-07-embedding-model-selection.md` | Default local embedding model: `nomic-embed-text-v1.5` (768 dims). OpenAI default: `text-embedding-3-small` (1536 dims) |

---

## Naming Conventions

- **Config keys (YAML):** `snake_case` — e.g., `scoring.weight_career_overlap`
- **Env vars:** `LINKEDOUT_UPPER_SNAKE_CASE` — e.g., `LINKEDOUT_SCORING__WEIGHT_CAREER_OVERLAP`
- **Pydantic fields:** `snake_case` — matching YAML keys
- **Nested config:** Use nested pydantic models (e.g., `ScoringConfig`, `EnrichmentConfig`). Double underscore `__` for env var nesting. **Convention (review finding 2026-04-07):** Nest config only when a group has 3+ related fields (e.g., `ScoringConfig` with 5 weights). Single standalone fields stay flat on `LinkedOutSettings`. This prevents unnecessary nesting while keeping related config grouped.
- **Industry-standard vars:** Keep standard names without prefix — `DATABASE_URL`, `OPENAI_API_KEY`, `APIFY_API_KEY`, `LANGFUSE_*`

---

## Shared File: `backend/src/shared/config/config.py`

**CRITICAL:** Multiple sub-phases add fields to this file. Each sub-phase adds its own nested pydantic model (e.g., `ScoringConfig`, `EnrichmentConfig`, `LLMConfig`). The `LinkedOutSettings` class gains a field for each nested model.

**Pattern for adding a new config section:**

```python
from pydantic import BaseModel

class ScoringConfig(BaseModel):
    """Affinity scoring weights and thresholds."""
    weight_career_overlap: float = 0.40
    weight_external_contact: float = 0.25
    # ... etc

class LinkedOutSettings(BaseSettings):
    # ... existing fields ...
    scoring: ScoringConfig = ScoringConfig()  # nested model with defaults
```

Sub-phases are serialized (SP2 → SP3 → SP4 → SP5) to avoid merge conflicts on this file.

---

## Constraints

1. **No behavioral changes** — Default values MUST match current hardcoded values exactly. This phase moves values, not changes them. Exception: log rotation (500MB→50MB, 10d→30d) which aligns with the approved decision doc.
2. **Apify Actor ID stays hardcoded** — `LpVuK3Zozwuipa5bp` is a named constant, NOT configurable. Changing it breaks response parsing. Include explanation comment and Apify marketplace link.
3. **Nanoid sizes stay hardcoded** — ID format constants (21 chars, 8 chars, entity prefixes) are data-format constants, not user-tunable.
4. **Voyager decoration IDs stay hardcoded** — Fragile LinkedIn internals, documented but not configurable.
5. **Tenant/BU/User IDs stay hardcoded** — Single-user OSS, system defaults.
6. **Embedding dimension validation** — On startup, detect dimension mismatch, warn loudly, suggest `linkedout embed --force`. Wrong dimensions silently break similarity search.

---

## Verification Commands

After all sub-phases complete, these commands should return zero results (verifying no hardcoded constants remain in business logic):

```bash
# No hardcoded model names outside config
grep -rn "gpt-5\|gpt-4\|text-embedding" backend/src/ --include="*.py" | grep -v config.py | grep -v __pycache__

# No hardcoded localhost URLs outside config
grep -rn "localhost:8001" backend/src/ --include="*.py" | grep -v config.py

# No hardcoded embedding dimensions outside config and entity files
grep -rn "= 1536" backend/src/ --include="*.py" | grep -v config.py | grep -v entities/

# Extension configurable constants are in config.ts, not elsewhere
grep -rn "STALENESS_DAYS\|HOURLY_LIMIT\|DAILY_LIMIT" extension/lib/ --include="*.ts" | grep -v config.ts | grep -v constants.ts
```

---

## Sub-Phase Dependency Graph

```
SP1 (Audits) ──┬──► SP2 (Scoring) ──► SP3 (Enrichment) ──► SP4 (LLM/Embed) ──► SP5 (Infra) ──┬──► SP7 (Docs)
               └──► SP6 (Extension Extraction) ─────────────────────────────────────────────────┘
```

- **SP1:** Read-only audits (backend + extension). No code changes.
- **SP2–SP5:** Backend config extractions. Serialized due to shared `config.py`.
- **SP6:** Extension extraction. Independent of SP2–SP5 (different codebase). Can run in parallel.
- **SP7:** Documentation. Depends on all prior sub-phases.

---

## Agents & Skills to Leverage

The following `.claude/agents/` and `.claude/skills/` are available and SHOULD be invoked during sub-phase execution where applicable:

### Skills (apply to ALL sub-phases)
| Skill | When to Invoke |
|-------|---------------|
| `.claude/skills/python-best-practices/SKILL.md` | When modifying `config.py`, adding nested pydantic models |
| `.claude/skills/docstring-best-practices/SKILL.md` | When creating new config classes (`ScoringConfig`, `EnrichmentConfig`, `LLMConfig`) |
| `.claude/skills/mvcs-compliance/SKILL.md` | When modifying service/config layers to use new config — layer responsibility rules |

### Notes
- Phase 4 is config extraction only — no new entities, schemas, or CRUD operations
- CRUD agents don't apply; this phase moves existing values to config, not creating new features

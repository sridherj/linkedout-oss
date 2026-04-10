# SP3: Engineering Principles — `/linkedout-dev` Skill

**Phase:** 01 — OSS Repository Scaffolding
**Sub-phase:** 3 of 5
**Dependencies:** SP2 (CONTRIBUTING.md must exist — this skill is linked from it)
**Estimated effort:** ~45 minutes
**Shared context:** `_shared_context.md`

---

## Scope

Create the `/linkedout-dev` skill that codifies LinkedOut's engineering principles. This is a living document consumed by AI agents (Claude Code, Codex, Copilot) and human contributors. It defines "how we build things here."

**Tasks from phase plan:** 1K

---

## Required Reading Before Starting

You MUST read ALL of these decision docs — this skill synthesizes principles from all of them:

1. `docs/decision/cli-surface.md` — CLI design principles, Operation Result Pattern, flat namespace
2. `docs/decision/env-config-design.md` — Config hierarchy, `~/linkedout-data/`, `LINKEDOUT_` prefix
3. `docs/decision/logging-observability-strategy.md` — loguru, structured logging, per-component logs, report framework
4. `docs/decision/queue-strategy.md` — No Procrastinate, synchronous execution
5. `docs/decision/2026-04-07-data-directory-convention.md` — Data directory convention
6. `docs/decision/2026-04-07-embedding-model-selection.md` — nomic-embed-text-v1.5 default
7. `docs/decision/2026-04-07-skill-distribution-pattern.md` — SKILL.md manifest standard

---

## Task 1K: `/linkedout-dev` Skill

**File to create:** `skills/linkedout-dev/SKILL.md`

### Content Sections

1. **Overview**
   - This skill defines LinkedOut's engineering standards
   - Reference it when writing code, reviewing PRs, or building new features
   - Consumed by AI agents and human contributors alike

2. **Zero Silent Failures**
   - Every operation must succeed completely or fail loudly with actionable diagnostics
   - No step in any flow should fail silently
   - Errors must include: what failed, why, what the user can do about it
   - Reference: `docs/decision/logging-observability-strategy.md` Section 12

3. **Quantified Readiness (Not Boolean)**
   - "Done" is never yes/no — it's precise counts
   - Pattern: "3,847/4,012 profiles have embeddings, 156 companies missing aliases"
   - Every major operation produces a readiness report with exact numbers
   - Reports persisted to `~/linkedout-data/reports/`
   - Reference: `docs/decision/logging-observability-strategy.md` Section 11

4. **Operation Result Pattern**
   - Every CLI command output follows: Progress -> Summary -> Failures (with reasons) -> Report path
   - Use the `OperationResult` class (to be built in Phase 3)
   - Commands never exit silently with just "Done"
   - Reference: `docs/decision/cli-surface.md` "Operation Result Pattern" section
   - Include the concrete output example from the decision doc

5. **Idempotency & Auto-Repair**
   - Every operation must be safe to re-run
   - Re-running a step should fix incomplete state, not corrupt it
   - Pattern: detect gap -> report gap -> offer to fix -> repair -> report results
   - `--dry-run` on every write command (from `docs/decision/cli-surface.md`)

6. **Structured Logging**
   - Use `get_logger(__name__)` from `shared/utilities/logger.py` (loguru-based)
   - Every log entry binds: `component`, `operation`, `correlation_id`
   - Human-readable log format (structured data goes to reports/metrics, not logs)
   - Per-component log files in `~/linkedout-data/logs/`
   - Reference: `docs/decision/logging-observability-strategy.md`

7. **CLI Design**
   - Flat `linkedout` namespace (no subgroups)
   - `--dry-run` on every write command
   - `--json` where skills need machine-readable output
   - Auto-detection over explicit flags where possible
   - Short, verb-first, hyphen-separated command names
   - Reference: `docs/decision/cli-surface.md`

8. **Configuration**
   - Three-layer hierarchy: env vars > config.yaml > secrets.yaml > defaults
   - `LINKEDOUT_` prefix for LinkedOut-specific vars
   - Industry-standard names kept as-is (`DATABASE_URL`, `OPENAI_API_KEY`)
   - All config under `~/linkedout-data/` (unified directory)
   - Reference: `docs/decision/env-config-design.md`

9. **Testing**
   - Tests must pass without external API keys
   - Mock LLM/API calls in unit tests
   - Integration tests use real PostgreSQL (pgvector Docker image in CI)
   - Three tiers: static (ruff, pyright), integration (real DB), installation (nightly)

### Format Requirements
- This is a `SKILL.md` file — it will be consumed by AI agents
- Keep it actionable and specific (not vague platitudes)
- Include concrete code/output examples where they clarify the principle
- Reference decision docs by relative path for traceability (e.g., `docs/decision/cli-surface.md`)
- Each principle should have: what, why, how, and a reference

### Hard Constraints
- No references to Procrastinate (mention synchronous execution if queues come up)
- No references to Docker for development (only mention pgvector Docker image in CI context)
- No references to internal tools (TaskOS, Langfuse by default)
- `nomic-embed-text-v1.5` is the default local model (not MiniLM)

---

## Post-Task: Update CONTRIBUTING.md Link

After creating the skill, verify that CONTRIBUTING.md (from SP2) contains a link to `skills/linkedout-dev/SKILL.md`. If the link is missing or broken, add/fix it.

The section in CONTRIBUTING.md should read something like:
```markdown
## Engineering Principles

See the [`/linkedout-dev` skill](skills/linkedout-dev/SKILL.md) for detailed engineering standards
including logging patterns, CLI output format, testing requirements, and configuration conventions.
```

---

## Verification

- [ ] File exists at `skills/linkedout-dev/SKILL.md`
- [ ] All 8 engineering principles from the phase plan are covered (Zero Silent Failures, Quantified Readiness, Operation Result Pattern, Idempotency, Structured Logging, CLI Design, Configuration, Testing)
- [ ] Each principle references its source decision doc by path
- [ ] Concrete examples included (not just abstract rules)
- [ ] CONTRIBUTING.md links to this skill
- [ ] No prohibited references (Procrastinate, Docker for dev, internal tools, MiniLM)

---

## Output Artifacts

- `skills/linkedout-dev/SKILL.md`
- `CONTRIBUTING.md` (updated link if needed)

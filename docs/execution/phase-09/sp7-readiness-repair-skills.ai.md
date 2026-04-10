# Sub-Phase 7: Readiness, Repair & Skills

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9M (Quantified Readiness Check), 9N (Gap Detection & Auto-Repair), 9O (Skill Installation)
**Dependencies:** sp6 (embeddings + affinity computed)
**Blocks:** sp8
**Can run in parallel with:** —

## Objective
Build the readiness report generator, gap detection/auto-repair module, and skill installation module. These three are grouped as the "post-computation validation and finalization" stage: readiness checks what's done, repair fixes gaps, and skill installation is the final "make it usable" step.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9M + 9N + 9O sections): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md` (use exact report format)
- Read logging strategy: `docs/decision/logging-observability-strategy.md`
- Read skill distribution pattern: `docs/decision/2026-04-07-skill-distribution-pattern.md`
- Read Phase 8 skill system: `docs/plan/phase-08-skill-system.md`
- Read Phase 8 execution: `docs/execution/phase-08/_shared_context.md`

## Deliverables

### 1. `backend/src/linkedout/setup/readiness.py` (NEW)

Quantified readiness report — NOT a pass/fail boolean. This is the definitive "is setup complete?" artifact.

**JSON report structure:**
```json
{
  "operation": "setup-readiness",
  "timestamp": "2026-04-07T14:30:00Z",
  "linkedout_version": "0.1.0",
  "counts": {
    "profiles_loaded": 4012,
    "profiles_with_embeddings": 3998,
    "profiles_without_embeddings": 14,
    "companies_loaded": 52000,
    "companies_missing_aliases": 156,
    "role_aliases_loaded": 2847,
    "connections_with_affinity": 3870,
    "connections_without_affinity": 0,
    "seed_tables_populated": 10
  },
  "coverage": {
    "embedding_coverage_pct": 99.7,
    "affinity_coverage_pct": 100.0,
    "company_match_pct": 95.9
  },
  "config": {
    "embedding_provider": "openai",
    "data_dir": "~/linkedout-data",
    "db_connected": true,
    "openai_key_configured": true,
    "apify_key_configured": false,
    "agent_context_env_exists": true
  },
  "gaps": [
    {"type": "missing_embeddings", "count": 14, "detail": "14 profiles have no embedding vector"},
    {"type": "missing_company_aliases", "count": 156, "detail": "156 companies have no aliases"}
  ],
  "next_steps": [
    "Run `linkedout embed` to generate embeddings for 14 remaining profiles",
    "Try: `/linkedout \"who do I know at Stripe?\"`"
  ]
}
```

**Console output:** Human-readable summary derived from the JSON (use exact format from UX design doc):
```
╔══════════════════════════════════════════════╗
║         LinkedOut Setup — Readiness          ║
╚══════════════════════════════════════════════╝

  Profiles:     4,012 loaded | 3,998 with embeddings (99.7%)
  Companies:    52,000 loaded | 95.9% of connections matched
  Affinity:     3,870 / 3,870 connections scored (100%)
  Config:       OpenAI embeddings | ~/linkedout-data/

  Gaps:
    ⚠ 14 profiles without embeddings
    ⚠ 156 companies without aliases

  Next steps:
    → Run `linkedout embed` to cover remaining 14 profiles
    → Try: /linkedout "who do I know at Stripe?"

  Report saved: ~/linkedout-data/reports/setup-readiness-20260407-143000.json
```

**Key functions:**
- `collect_readiness_data(db_url: str, data_dir: Path) -> dict` — gather all counts from DB and config
- `compute_coverage(data: dict) -> dict` — calculate coverage percentages
- `detect_gaps(data: dict) -> list[dict]` — identify gaps with actionable descriptions
- `suggest_next_steps(gaps: list[dict]) -> list[str]` — generate next steps
- `generate_readiness_report(db_url: str, data_dir: Path) -> ReadinessReport` — full report
- `format_console_report(report: ReadinessReport) -> str` — human-readable console output
- `save_report(report: ReadinessReport, data_dir: Path) -> Path` — persist JSON to reports dir

**Integration:**
- Uses Phase 3 `OperationReport` format
- Queries database for counts (profiles, companies, embeddings, affinity)
- Reads config files for config status
- Report format consistent with Phase 3K specification

### 2. `backend/src/linkedout/setup/auto_repair.py` (NEW)

Gap detection and offer-to-fix module.

**Implementation:**

1. **Read readiness report** from readiness module

2. **For each gap type, offer repair:**
   - **Missing embeddings:** "Found N profiles without embeddings. Generate now? [Y/n]" → `linkedout embed`
   - **Missing affinity scores:** "Found N connections without affinity scores. Compute now? [Y/n]" → `linkedout compute-affinity --force`
   - **Stale embeddings (wrong provider):** "Found N profiles with [old] embeddings but config is set to [new]. Re-embed? [y/N]" (default NO — expensive)

3. **After repairs:** Re-run readiness check to produce updated report

4. **Idempotent:** Each repair only processes items that actually need fixing

**Key functions:**
- `analyze_gaps(report: ReadinessReport) -> list[RepairAction]`
- `prompt_repair(action: RepairAction) -> bool` — ask user, return True if accepted
- `execute_repair(action: RepairAction) -> OperationReport`
- `run_auto_repair(report: ReadinessReport, data_dir: Path) -> ReadinessReport` — full cycle: analyze → prompt → repair → re-check

**Repair action types:**
```python
@dataclass
class RepairAction:
    gap_type: str           # "missing_embeddings", "missing_affinity", "stale_embeddings"
    description: str        # Human-readable description
    command: str            # CLI command to run
    default_accept: bool    # True = [Y/n], False = [y/N]
    estimated_time: str     # "~2 minutes"
    estimated_cost: str | None  # "$0.01" or None
```

### 3. `backend/src/linkedout/setup/skill_install.py` (NEW)

Skill detection and installation module.

**Implementation:**

1. **Detect installed platforms:**
   - Claude Code: check for `~/.claude/` directory
   - Codex: check for `~/.agents/` directory (or equivalent Codex config)
   - Copilot: check for `~/.copilot/` or `~/.github/` directory

2. **For each detected platform:**
   - Generate skills from templates: run `bin/generate-skills` (Phase 8)
   - Copy/symlink generated skills to platform directory:
     - Claude Code: `~/.claude/skills/linkedout/`
     - Codex: `~/.agents/skills/linkedout/`
     - Copilot: `~/.github/skills/linkedout/`
   - Verify: skill files exist at target location

3. **CLAUDE.md / AGENTS.md update:**
   - Add routing rules to the platform's dispatch file
   - Include path to `agent-context.env` so skills can find DB credentials

4. **Report:** "Skills installed for: Claude Code, Codex. Try: /linkedout \"who do I know at Stripe?\""

**Key functions:**
- `detect_platforms() -> list[PlatformInfo]` — detect installed AI platforms
- `generate_skills(repo_root: Path) -> bool` — run `bin/generate-skills`
- `install_skills_for_platform(platform: PlatformInfo, repo_root: Path) -> bool`
- `update_dispatch_file(platform: PlatformInfo, agent_context_path: Path) -> bool`
- `setup_skills(repo_root: Path, data_dir: Path) -> OperationReport` — full orchestration

**Idempotency:**
- Re-running updates skills (handles upgrades)
- Missing platform skipped gracefully with informational message

### 4. Unit Tests

**`backend/tests/linkedout/setup/test_readiness.py`** (NEW)
- `collect_readiness_data()` returns dict with all expected keys (mock DB)
- `compute_coverage()` calculates correct percentages
- `detect_gaps()` identifies missing embeddings when count > 0
- `detect_gaps()` returns empty list when everything is 100%
- `format_console_report()` produces box-drawing output
- `save_report()` writes valid JSON to expected path
- Report JSON contains all fields from the schema above
- No API keys or passwords in report output

**`backend/tests/linkedout/setup/test_auto_repair.py`** (NEW)
- `analyze_gaps()` identifies missing embeddings gap
- `analyze_gaps()` returns empty list when no gaps
- `execute_repair()` calls correct CLI command (mock)
- Repair actions have correct default_accept values

**`backend/tests/linkedout/setup/test_skill_install.py`** (NEW)
- `detect_platforms()` detects Claude Code when `~/.claude/` exists (mock)
- `detect_platforms()` returns empty list when no platforms found (mock)
- `generate_skills()` calls `bin/generate-skills` (mock subprocess)
- `install_skills_for_platform()` copies files to correct directory (mock/temp dir)

## Verification
1. `python -c "from linkedout.setup.readiness import generate_readiness_report"` imports without error
2. `python -c "from linkedout.setup.auto_repair import run_auto_repair"` imports without error
3. `python -c "from linkedout.setup.skill_install import detect_platforms"` imports without error
4. `pytest backend/tests/linkedout/setup/test_readiness.py -v` passes
5. `pytest backend/tests/linkedout/setup/test_auto_repair.py -v` passes
6. `pytest backend/tests/linkedout/setup/test_skill_install.py -v` passes

## Notes
- The readiness report is the single most important artifact of the setup flow. It must be precise (numbers, not "done"), comprehensive (all dimensions), and actionable (gaps have fixes).
- Readiness report must NEVER contain API keys, passwords, or LinkedIn URLs. Config section only shows whether keys are configured (boolean), not the values.
- Auto-repair is interactive — user is prompted before each repair. No silent actions.
- Skill installation depends on Phase 8 being complete. If `bin/generate-skills` doesn't exist, skip with a clear message.
- Platform detection should be conservative — only claim a platform is installed if the config directory actually exists.
- Use exact console output format from UX design doc (sp1) for the readiness report.

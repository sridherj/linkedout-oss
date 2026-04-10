# Open Questions — Resolved Decisions

**Date:** 2026-04-07
**Decided by:** SJ (interview session with fanout-detailed-plan agent)

All open questions from the 13 detailed phase plans, resolved in a single interview session.

---

## Phase 1: OSS Repository Scaffolding

| # | Question | Decision | Notes |
|---|----------|----------|-------|
| 1 | GitHub org/owner | `sridherj/linkedout-oss` | Personal account. Can transfer to org later (GitHub redirects). |
| 2 | CoC enforcement contact | GitHub Security Advisories only | No email. Revisit if contributor volume grows. |
| 3 | CI Python versions | 3.12 only in Phase 1 | Expand to 3.11/3.12/3.13 matrix in Phase 13. |
| 4 | Backend test suite in CI | Ruff + pyright only in Phase 1 | Pytest deferred to Phase 6 (depends on Procrastinate removal). |
| 5 | Extension test suite in CI | Skip until Phase 12 | Extension isn't touched until then. |
| 6 | PR template | Yes, add in Phase 1 | Standard Summary / Test plan / Checklist template. |
| 7 | Pre-commit hooks | Defer to Phase 6 | Document in CONTRIBUTING.md, ship config when codebase is clean. |

**Additional decision:** Project uses `uv` and `requirements.txt` — make this explicit in all docs.

---

## Phase 4: Constants Externalization

| # | Question | Decision | Notes |
|---|----------|----------|-------|
| 1 | Scoring config granularity | Expose everything (all weights, seniority boosts, recency thresholds) | Add thorough comments in config. Users who want to tune can tune. |
| 2 | Embedding dimension mismatch | Detect on startup, warn loudly, suggest `linkedout embed --force` | Wrong-dimension embeddings silently break search. |
| 3 | Extension options page timing | Acceptable — DevTools editing until Phase 12 | No users between Phase 4 and Phase 12. |
| 4 | Apify Actor ID | Keep hardcoded as a named constant with explanation/link | Not configurable — changing it breaks parsing. Document why. |
| 5 | Log rotation mismatch | Phase 3 fixes defaults (50MB/30d), Phase 4 externalizes as config vars | Clean separation: Phase 3 = correctness, Phase 4 = configurability. Phase 4 runs after Phase 3. |

---

## Phase 5: Embedding Provider Abstraction

| # | Question | Decision | Notes |
|---|----------|----------|-------|
| 1 | Batch API default | Real-time API default, `--batch` flag for cost-conscious users | Better UX — instant progress bar. Cost difference on 4K profiles is pennies. |
| 2 | `auto` provider selection | No `auto` mode — explicit choice required | User picks during setup. Error if not configured. "If OpenAI key is present, always leverage that." |
| 3 | Nomic model download timing | During setup (synchronous with progress bar) | Download happens right after user picks local provider. Next step (embed) needs it immediately. |
| 4 | Failed embeddings file location | `~/linkedout-data/reports/` | Operation artifact, not a log stream. Consistent with other reports. |
| 5 | Dual-column cleanup | Defer — not worth the complexity for v1 | 50MB is negligible. Power users can run SQL. |
| 6 | HNSW index build time | Include in migration | Fresh installs = empty table (instant). Upgrades pay one-time cost. Required for query performance. |

**Additional context:** When semantic search is invoked, the query text must be embedded in real-time to compare against stored profile embeddings. This is a single API call per query (cheap, fast). The active provider determines which embedding column is searched. If OpenAI key is present, use it for query embedding regardless.

---

## Phase 6: Code Cleanup for OSS

| # | Question | Decision | Notes |
|---|----------|----------|-------|
| 1 | `common/` module scope | Investigate during implementation, delete only if confirmed unused | Grep before deleting. Don't decide blind. |
| 2 | `utilities/prompt_manager/` | Keep it | SJ decision. |
| 3 | Alembic migrations for dropped tables | One-way only (drop, no recreate) | **Expanded decision:** Replace entire migration history with a single fresh baseline migration for OSS. Includes: all tables, all indexes (HNSW, GIN, etc.), `CREATE EXTENSION IF NOT EXISTS` for vector and pg_trgm, `DROP TABLE IF EXISTS` for externally-created tables (e.g., Procrastinate). Some tables may appear in old migrations for autogenerate compatibility — the baseline replaces all of this. |
| 4 | `shared/test_endpoints/sse_router.py` | Remove | Spike artifact. If SSE is needed later, build it properly against requirements. |
| 5 | Firebase auth provider code | Keep as-is, add comment | Comment: `# Firebase auth preserved for potential multi-user support — see Phase 0B decision.` |
| 6 | `dev_tools/` after CLI refactor | Move implementation files to `linkedout/commands/`, delete `dev_tools/cli.py` | Clean break. Phase 6 is literally the cleanup phase. |
| 7 | `organization/` module | Keep — DO NOT REMOVE | Actively used. Load-bearing tenant/BU/enrichment_config infrastructure. Make this explicit in the plan. |

---

## Phase 8: Skill System & Distribution

| # | Question | Decision | Notes |
|---|----------|----------|-------|
| 1 | Generated skill files in git | Yes — track in git | Users can install directly from clone. CI check (`bin/generate-skills --check`) catches drift. Matches gstack pattern. |
| 2 | Copilot skill format | Implement based on current docs, flag as "beta" | Near-zero marginal effort. Three platforms at launch looks better than two. |
| 3 | Schema reference maintenance | Auto-generate from existing `build_schema_context()` | `schema_context.py` already introspects SQLAlchemy entities. `bin/generate-schema-ref` is a 10-line script wrapping it. |
| 4 | Skill prefix toggle | No — `/linkedout` is the only prefix | No configurability needed. No consumer for this. |
| 5 | Agent tool in skills | Core `/linkedout` skill should leverage Agent tool for parallel query execution | Queries take 30s-1min. Parallelizing independent lookups meaningfully cuts response time. Simple utility skills stay sequential. |
| 6 | Extension setup skill stub | Don't create — Phase 12 builds it | Make this explicit in Phase 12 doc. No stubs. |

---

## Phase 12: Chrome Extension Add-on

| # | Question | Decision | Notes |
|---|----------|----------|-------|
| 1 | Minimum Chrome version | Chrome 114+, with version check on install | 5 lines of code. Shows clear error instead of cryptic API failure. |
| 2 | Extension distribution format | Ship zip. Skill unzips to `~/linkedout-data/extension/chrome/`, user does "Load unpacked". | One artifact, one path, one set of instructions. |
| 3 | Backend auto-start | Manual `linkedout start-backend` for v1 | Extension must detect "backend unreachable" and show actionable message: `Backend not running. Run "linkedout start-backend" or ask /linkedout-setup-report to diagnose.` |
| 4 | Extension update flow | Overwrite fixed path + instruct user to click refresh on `chrome://extensions` | Unzip new version to same `~/linkedout-data/extension/chrome/` path. One-click refresh. |
| 5 | `stop-backend` visibility | User-facing in `--help` as convenience command | Not part of the 13-command contract. Natural pair with `start-backend`. |

**Additional decisions:**
- `start-backend` must be idempotent: detect existing process on port, kill it, then start fresh. No "address already in use" errors.
- `/linkedout-extension-setup` skill is created in Phase 12 (not stubbed in Phase 8). Make explicit in Phase 12 plan.

---

## Phases with No Open Questions

Phases 2, 3, 7, 9, 10, 11, 13 — all self-contained, no human action needed.

# Sub-Phase 6: Computation Steps (Embeddings + Affinity)

**Phase:** 9 — AI-Native Setup Flow
**Plan tasks:** 9K (Embedding Generation), 9L (Affinity Computation)
**Dependencies:** sp5 (data must be imported before computation)
**Blocks:** sp7
**Can run in parallel with:** —

## Objective
Build the embedding generation and affinity computation orchestration modules. These wrap existing CLI commands with setup-specific UX: time/cost estimates, progress tracking, and result summaries. Grouped together because both are "compute over imported data" steps that run sequentially after data import.

## Context
- Read shared context: `docs/execution/phase-09/_shared_context.md`
- Read plan (9K + 9L sections): `docs/plan/phase-09-setup-flow.md`
- Read UX design doc: `docs/design/setup-flow-ux.md` (use exact wording)
- Read embedding model decision: `docs/decision/2026-04-07-embedding-model-selection.md`
- Read existing embedding code: `backend/src/linkedout/` (find EmbeddingProvider and related)
- Read existing affinity code: `backend/src/linkedout/intelligence/scoring/`

## Deliverables

### 1. `backend/src/linkedout/setup/embeddings.py` (NEW)

Embedding generation orchestration for the setup flow.

**Implementation:**

1. **Provider selection:** Read from config (set in sp4/9F): `openai` or `local`

2. **Pre-generation info:**
   - Count profiles needing embeddings (query DB)
   - Estimate time:
     - OpenAI Batch API: ~minutes for 4K profiles
     - Local nomic: ~X seconds per profile on CPU (benchmark on startup or use conservative estimate)
   - Estimate cost: OpenAI ~$0.02 per 1K profiles
   - Show: "Generating embeddings for N profiles using [provider]. Estimated time: ~X minutes."

3. **Confirmation:** Ask user to confirm before starting (especially for OpenAI — costs money)

4. **Execute:** Run `linkedout embed --provider <provider>`
   - Progress bar with profile count
   - Resumable — if interrupted, picks up where it left off (Phase 5 progress tracking)

5. **Result:** Show embedding output summary: profiles embedded, duration, provider, dimension

**Key functions:**
- `count_profiles_needing_embeddings(db_url: str) -> int`
- `estimate_embedding_time(count: int, provider: str) -> str` — human-readable estimate
- `estimate_embedding_cost(count: int, provider: str) -> str | None` — cost string or None for free
- `run_embeddings(provider: str) -> OperationReport` — execute with progress
- `setup_embeddings(data_dir: Path, db_url: str) -> OperationReport` — full orchestration

**Idempotency:**
- Only embeds profiles without embeddings
- Re-running after interruption resumes from where it stopped
- Uses Phase 5 progress tracking at `~/linkedout-data/state/embedding_progress.json`

### 2. `backend/src/linkedout/setup/affinity.py` (NEW)

Affinity computation orchestration for the setup flow.

**Implementation:**

1. **Pre-computation check:** Verify user profile exists (set in sp4/9G) — required as affinity anchor. If missing, return error pointing user to re-run user profile setup.

2. **Execute:** Run `linkedout compute-affinity`
   - Progress: "Computing affinity scores... X/Y connections"

3. **Result summary:**
   - Profiles scored, tier distribution:
     - Inner circle (Dunbar tier 1)
     - Close (Dunbar tier 2)
     - Active (Dunbar tier 3)
     - Peripheral (Dunbar tier 4+)
   - Brief explanation of what the tiers mean

**Key functions:**
- `check_user_profile_exists(db_url: str) -> bool`
- `run_affinity_computation() -> OperationReport` — execute with progress
- `format_tier_distribution(report: OperationReport) -> str` — human-readable tier summary
- `setup_affinity(data_dir: Path, db_url: str) -> OperationReport` — full orchestration

**Idempotency:**
- Re-running recomputes only unscored connections (unless `--force`)
- Safe to re-run — doesn't corrupt existing scores

### 3. Unit Tests

**`backend/tests/linkedout/setup/test_embeddings.py`** (NEW)
- `count_profiles_needing_embeddings()` returns correct count (mock DB)
- `estimate_embedding_time(1000, "openai")` returns a human-readable string
- `estimate_embedding_time(1000, "local")` returns a longer estimate than openai
- `estimate_embedding_cost(1000, "openai")` returns cost string (e.g., "~$0.02")
- `estimate_embedding_cost(1000, "local")` returns None (free)
- `run_embeddings()` calls correct CLI command with provider flag (mock)
- Result report includes profiles_embedded, duration, provider fields

**`backend/tests/linkedout/setup/test_affinity.py`** (NEW)
- `check_user_profile_exists()` returns True when profile exists (mock DB)
- `check_user_profile_exists()` returns False when no profile (mock DB)
- `setup_affinity()` fails with clear error when no user profile
- `run_affinity_computation()` calls correct CLI command (mock)
- `format_tier_distribution()` produces human-readable output
- Result report includes profiles_scored, tier counts

## Verification
1. `python -c "from linkedout.setup.embeddings import estimate_embedding_cost; print(estimate_embedding_cost(1000, 'openai'))"` prints cost estimate
2. `python -c "from linkedout.setup.affinity import setup_affinity"` imports without error
3. `pytest backend/tests/linkedout/setup/test_embeddings.py -v` passes
4. `pytest backend/tests/linkedout/setup/test_affinity.py -v` passes

## Notes
- These modules are orchestration wrappers — they call existing CLI commands, not the embedding/affinity logic directly.
- Time estimates should be conservative (overestimate rather than underestimate).
- OpenAI cost estimates use current Batch API pricing for text-embedding-3-small.
- The affinity module must check for user profile BEFORE starting computation — failing mid-way through is worse than failing at the start.
- Progress display should use the same format as the UX design doc (sp1).
- Both modules use sp2 logging infrastructure (`get_setup_logger()`).

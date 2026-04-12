# Enrichment CLI: Progress Reporting, Smart Errors, and Post-Import Guidance

## Overview

The enrichment pipeline exists as an API endpoint but has no CLI command. After `linkedout import-connections`, users are told to run `embed` and `compute-affinity` but never told to enrich — the most valuable next step. When enrichment runs (via setup or API), there's no progress reporting, no Apify-specific error handling, and no awareness that credits might be exhausted across multiple keys.

This plan adds a `linkedout enrich` CLI command with periodic progress output, Apify-specific error handling (402 payment required, 429 rate limit), per-key health tracking (skip exhausted keys, report cleanly), and updates `import-connections` to recommend enrichment first.

## Operating Mode

**HOLD SCOPE** — Focused on CLI + error handling. No changes to the API endpoint's contract, no new async/background job infrastructure, no BYOK changes.

## Sub-phase 1: `linkedout enrich` CLI Command with Progress Reporting

**Outcome:** `linkedout enrich` enriches all unenriched profiles (or a subset via `--limit`), printing periodic progress lines during the run. The user sees how many profiles have been enriched, how many remain, cost so far, and estimated time remaining.

**Dependencies:** None

**Estimated effort:** 1 session (~2.5 hours)

**Verification:**
- `linkedout enrich` with unenriched profiles prints progress every N profiles
- `linkedout enrich --limit 50` enriches only 50 profiles
- `linkedout enrich` with 0 unenriched profiles prints "All profiles are enriched" and exits
- `linkedout enrich --dry-run` shows how many profiles would be enriched and estimated cost without calling Apify
- Progress output includes: enriched/total, cost so far, elapsed time, estimated remaining

Key activities:

- **Create `backend/src/linkedout/commands/enrich.py`**: New Click command `linkedout enrich` with options:
  - `--limit N`: Max profiles to enrich (default: all unenriched — no confirmation prompt, users who want to check cost first use `--dry-run`)
  - `--dry-run`: Count unenriched profiles, estimate cost, print summary, exit without calling Apify
  - No `--verbose` — progress reporting is always on since enrichment is a long-running operation

- **Enrichment flow**: The command builds its own loop — it does NOT reuse `_EnrichmentTriggerService` (which is entangled with HTTP context). The loop:
  1. Queries unenriched profiles via raw SQL (same pattern as `embed`'s `fetch_profiles_needing_embeddings`)
  2. For each profile, calls `LinkedOutApifyClient.enrich_profile_sync()` directly
  3. Delegates to `PostEnrichmentService.process_enrichment_result()` for the complex DB writes (~200 lines of Apify JSON parsing, experience/education row creation, company resolution)
  4. Creates `EnrichmentEventEntity` rows (audit trail) using SYSTEM_USER_ID/SYSTEM_TENANT/SYSTEM_BU — so diagnostics and `/stats` show complete history regardless of CLI vs API trigger
  5. Commits per-profile for Ctrl+C durability
  
  The heavy lifting (PostEnrichmentService) is shared with the API endpoint. The ~30-line loop is CLI-specific. No refactoring of the API code path needed.

- **Progress reporting**: After every profile (or every N profiles for large batches), print a progress line:
  ```
  Enriching profiles...
    [  25/1000]  2.5% | $0.10 spent | 45s elapsed | ~28m remaining
    [  50/1000]  5.0% | $0.20 spent | 92s elapsed | ~27m remaining
    [ 100/1000] 10.0% | $0.40 spent | 3m elapsed  | ~25m remaining
  ```
  Print a new progress line every 25 profiles (not `\r` overwrite — works in all terminals, scrollback-friendly, pipeable, matches `import-connections` pattern). Before the loop, print the total cost estimate (like `embed` does): `Estimated cost: ~$54.30 (~$4.00 per 1,000 profiles)`. Print a final summary:
  ```
  Enrichment complete: 1,000 profiles enriched ($4.00, 28m 15s)
  
  Next steps:
    -> Run `linkedout embed` to generate embeddings for semantic search
    -> Run `linkedout compute-affinity` to calculate affinity scores
  ```

- **Dry-run output**:
  ```
  Dry run: 13,574 unenriched profiles found
  Estimated cost: $54.30 (~$4.00 per 1,000 profiles)
  Apify keys configured: 3 (round-robin)
  
  Run `linkedout enrich` to start enrichment.
  Run `linkedout enrich --limit 1000` to enrich a subset.
  ```

- **Register command** in `backend/src/linkedout/cli.py` under a new `--- Enrichment ---` section.

- **Handle missing Apify key gracefully**: Catch the `ValueError` from `get_platform_apify_key()` and print a clean Click error with setup instructions — no traceback:
  ```
  Error: No Apify API key configured.
  
  Set APIFY_API_KEY for a single key, or
  APIFY_API_KEYS=key1,key2,key3 for round-robin.
  
  Configure in secrets.yaml, .env, or environment variables.
  ```

- **Signal handler for Ctrl+C**: Follow `embed`'s pattern (embed.py:425-430) — install a SIGINT handler that sets an `interrupted` flag, exits the loop cleanly, and prints partial progress summary.

- **Update `LINKEDOUT_HELP_TEXT`** in `cli_helpers.py`: Add `enrich` to the Intelligence category: `Intelligence: enrich, compute-affinity, embed`.

- **Write unit tests**: `backend/tests/unit/test_enrich_command.py` — mock the Apify client, test progress output, dry-run, limit, empty state, signal handler (Ctrl+C triggers clean exit with partial progress), and no-key-configured error.

**Design review:**
- Spec consistency: Add `enrich` to `cli_commands.collab.md`.
- Architecture: The command builds its own ~30-line loop calling `ApifyClient` + `PostEnrichmentService` directly. Does NOT reuse `_EnrichmentTriggerService` (HTTP-coupled). Creates `EnrichmentEventEntity` rows for audit trail consistency.
- Session management: Each profile enrichment should commit independently so that progress is durable — if the user Ctrl+C's, already-enriched profiles stay enriched.

## Sub-phase 2: Apify-Specific Error Handling and Per-Key Health Tracking

**Outcome:** When an Apify key hits credit exhaustion (HTTP 402) or rate limits (429), the system detects it, marks that key as exhausted/throttled, rotates to the next key, and continues. When ALL keys are exhausted, enrichment stops cleanly with a clear message. Individual key failures (invalid key, 403) are also handled distinctly.

**Dependencies:** None (can run in parallel with Sub-phase 1)

**Estimated effort:** 1 session (~2 hours)

**Verification:**
- HTTP 402 from Apify → key marked as exhausted, next key tried
- All keys exhausted → enrichment stops with clear message showing which keys failed
- HTTP 429 → backoff and retry with same key (rate limit is temporary)
- HTTP 403 → key marked as invalid, skipped permanently
- After exhaustion, progress summary shows partial results
- Unit tests cover all error codes

Key activities:

- **Add `ApifyError` hierarchy to `apify_client.py`**:
  ```python
  class ApifyError(Exception):
      """Base class for Apify-specific errors."""
      def __init__(self, message: str, status_code: int | None = None):
          super().__init__(message)
          self.status_code = status_code

  class ApifyCreditExhaustedError(ApifyError):
      """HTTP 402 — account has no credits remaining."""

  class ApifyRateLimitError(ApifyError):
      """HTTP 429 — rate limit hit, retry after backoff."""

  class ApifyAuthError(ApifyError):
      """HTTP 401/403 — invalid or revoked API key."""
  ```

- **Update `enrich_profile_sync()` in `LinkedOutApifyClient`**: Instead of `return None` on `not resp.ok`, raise the appropriate `ApifyError` subclass based on status code. This gives callers the information to make smart retry/skip decisions.

- **Add `KeyHealthTracker` to `apify_client.py`**: Replace the simple `itertools.cycle` with a key manager that tracks per-key health:
  ```python
  class KeyHealthTracker:
      """Tracks which Apify keys are healthy, exhausted, or rate-limited."""
      
      def __init__(self, keys: list[str]):
          self._keys = keys
          self._exhausted: set[int] = set()  # indices of 402'd keys
          self._invalid: set[int] = set()    # indices of 401/403'd keys
          self._current = 0
      
      def next_key(self) -> str:
          """Return the next healthy key, or raise AllKeysExhaustedError."""
          ...
      
      def mark_exhausted(self, key: str) -> None: ...
      def mark_invalid(self, key: str) -> None: ...
      def healthy_count(self) -> int: ...
      def summary(self) -> str:
          """Human-readable status of all keys for error reporting."""
  ```

- **Update `get_platform_apify_key()`**: Return key from `KeyHealthTracker` instead of bare `itertools.cycle`. Expose `get_key_tracker()` for the CLI to query health status.

- **Update retry logic in `_run_enrichment()`** (or the new CLI's enrichment loop):
  - `ApifyCreditExhaustedError` → mark key exhausted, try next key immediately (no backoff)
  - `ApifyRateLimitError` → backoff 30s, retry **same key** (rate limits are temporary, per-account — rotating wouldn't help since the limit applies to the account, not the request)
  - `ApifyAuthError` → mark key invalid, try next key
  - `AllKeysExhaustedError` → stop enrichment cleanly, print partial progress summary, exit with code 1

- **Clean stop message** when all keys are exhausted:
  ```
  All Apify keys exhausted — stopping enrichment.
  
    Key 1 (…a3f4): credits exhausted (HTTP 402)
    Key 2 (…b7e2): credits exhausted (HTTP 402)
    Key 3 (…c9d1): credits exhausted (HTTP 402)
  
  Enriched 3,421 of 13,574 profiles ($13.68) before credits ran out.
  
  To continue:
    -> Add credits to your Apify account(s)
    -> Or add another key: set APIFY_API_KEYS=key1,key2,...,newkey
    -> Then re-run: linkedout enrich
  ```

- **Write unit tests**:
  - `backend/tests/unit/enrichment_pipeline/test_key_health_tracker.py` — test rotation, exhaustion marking, all-exhausted error, summary output.
  - `backend/tests/unit/enrichment_pipeline/test_apify_client.py` — test that `enrich_profile_sync()` raises `ApifyCreditExhaustedError` on HTTP 402, `ApifyRateLimitError` on 429, `ApifyAuthError` on 401/403, and returns `None` (or raises generic `ApifyError`) on other non-200 codes. Mock `requests.post` responses.

**Design review:**
- Backward compatibility: The `get_platform_apify_key()` API stays the same (returns a string). Callers that don't handle the new exceptions get the same behavior as before (generic exception caught by retry logic). The `KeyHealthTracker` is internal.
- Security: Key hints in error messages show only last 4 chars (`…a3f4`), never the full key.
- The existing API endpoint's retry logic in `controller.py` benefits from the new error hierarchy without code changes — the `except Exception` still catches everything, but logging now shows the specific Apify error type.

## Sub-phase 3: Update `import-connections` Next Steps

**Outcome:** After importing connections, the CLI recommends enrichment first (with cost estimate), then embed, then compute-affinity. The recommendation is contextual — only shown when unenriched profiles exist.

**Dependencies:** Sub-phase 1 (needs `linkedout enrich` to exist)

**Estimated effort:** 0.5 session (~45 min)

**Verification:**
- Import with unenriched profiles → shows enrichment as first next step with cost estimate
- Import where all profiles matched existing enriched data → skips enrichment recommendation
- Cost estimate is accurate based on unenriched count

Key activities:

- **Update `backend/src/linkedout/commands/import_connections.py`**: Change the next steps section (lines 284-293) to be contextual:
  ```python
  from shared.config import get_config
  
  next_steps = []
  if totals['unenriched'] > 0:
      cost_per = get_config().enrichment.cost_per_profile_usd
      cost = totals['unenriched'] * cost_per
      next_steps.append(
          f'Run `linkedout enrich` to fetch full profiles via Apify '
          f'(~${cost:.2f} for {totals["unenriched"]:,} profiles)'
      )
  next_steps.append('Run `linkedout embed` to generate embeddings for semantic search')
  next_steps.append('Run `linkedout compute-affinity` to calculate affinity scores')
  ```

- **Update the `OperationReport.next_steps`** to match.

- **Update existing unit test** if there's one testing next steps output.

**Design review:**
- The cost estimate reads `get_config().enrichment.cost_per_profile_usd` (default $0.004). If config changes, the estimate follows.
- Ordering: enrich → embed → compute-affinity reflects the actual dependency chain (enrichment provides the data that embeddings and affinity operate on).

## Sub-phase 4: Spec Updates and Integration Test

**Outcome:** CLI commands spec updated with `enrich` command. Integration test verifies the full flow: import → enrich (mocked Apify) → progress output → error handling.

**Dependencies:** Sub-phases 1-3

**Estimated effort:** 1 session (~1.5 hours)

**Verification:**
- `cli_commands.collab.md` documents the `enrich` command with all flags
- Integration test exercises: import → enrich --dry-run → enrich --limit 5 (mocked) → credit exhaustion scenario
- All existing enrichment tests pass

Key activities:

- **Update `docs/specs/cli_commands.collab.md`**: Add `enrich` command with `--limit`, `--dry-run` flags.
- **Write integration test**: `backend/tests/unit/enrichment_pipeline/test_enrich_cli_flow.py` — end-to-end CLI test with mocked Apify client.
- **Run full test suite**: `pytest backend/tests/unit/upgrade/ backend/tests/unit/enrichment_pipeline/ -v`

## Build Order

```
Sub-phase 1 (enrich CLI + progress) ──────┐
                                          ├──► Sub-phase 3 (import next steps) ──► Sub-phase 4 (specs + integration)
Sub-phase 2 (Apify error handling) ───────┘
```

**Parallelism:** Sub-phases 1 and 2 can run in parallel. Sub-phase 3 depends on Sub-phase 1. Sub-phase 4 depends on all.

## Resolved Decisions (2026-04-12)

| # | Decision | Resolution |
|---|----------|------------|
| 1 | Default behavior of `linkedout enrich` with no flags | Enrich ALL unenriched profiles. No confirmation prompt. Users check cost via `--dry-run` first. |
| 2 | All keys exhausted mid-run | Exit cleanly with partial progress summary. User re-runs after adding credits. No interactive pause. |
| 3 | HTTP 429 (rate limit) handling | Retry same key with 30s backoff. Rate limits are per-account and temporary — rotating keys wouldn't help. |
| 4 | Progress line format | New line every 25 profiles (not `\r` overwrite). Works in all terminals, scrollback-friendly, matches `import-connections`. |
| 5 | CLI enrichment loop architecture | Own ~30-line loop calling ApifyClient + PostEnrichmentService directly. Does NOT reuse `_EnrichmentTriggerService` (HTTP-coupled). |
| 6 | EnrichmentEventEntity audit rows from CLI | Yes — CLI creates audit rows using SYSTEM_USER_ID. Stats/diagnostics show complete history regardless of trigger source. |
| 7 | Cost estimation in import-connections next-steps | Read from `get_config().enrichment.cost_per_profile_usd`, not hardcoded `0.004`. |
| 8 | Missing Apify key UX | Catch ValueError, print clean Click error with setup instructions. No traceback. |
| 9 | Test coverage for error handling | Both signal handler test (Ctrl+C) and Apify error code tests (402/429/401/403 → correct exception subclass). |
| 10 | `enrich` in CLI help text | Under Intelligence category: `Intelligence: enrich, compute-affinity, embed`. |
| 11 | Cost estimate at run start | Print total estimate before loop starts (like `embed`): `Estimated cost: ~$54.30 (~$4.00 per 1,000 profiles)`. |

## Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Enrichment is slow (~60s per profile sync) | High for large networks | Progress reporting makes the wait tolerable. `--limit` allows incremental enrichment. |
| Apify changes their error codes | Low | Error handling falls back to generic retry on unrecognized status codes. Only 402/429/401/403 get special treatment. |
| Key rotation state is module-level (global) | Low | Single-user CLI tool — no concurrency concerns. `reset_key_cycle()` already exists for testing. |
| User Ctrl+C during enrichment loses progress | Med | Per-profile commit ensures enriched profiles are saved. Summary of partial progress on interrupt (signal handler). |

## Files Modified (Summary)

### New files

| File | Sub-phase | Description |
|------|-----------|-------------|
| `backend/src/linkedout/commands/enrich.py` | 1 | `linkedout enrich` CLI command |
| `backend/tests/unit/test_enrich_command.py` | 1 | Unit tests for enrich command |
| `backend/tests/unit/enrichment_pipeline/test_key_health_tracker.py` | 2 | Unit tests for key health tracking |
| `backend/tests/unit/enrichment_pipeline/test_apify_client.py` | 2 | Unit tests for Apify error code → exception mapping |
| `backend/tests/unit/enrichment_pipeline/test_enrich_cli_flow.py` | 4 | CLI flow test with mocked Apify |

### Modified files

| File | Sub-phase | Change |
|------|-----------|--------|
| `backend/src/linkedout/cli.py` | 1 | Register `enrich` command |
| `backend/src/linkedout/enrichment_pipeline/apify_client.py` | 2 | Add error hierarchy, `KeyHealthTracker`, update `enrich_profile_sync()` |
| `backend/src/linkedout/cli_helpers.py` | 1 | Add `enrich` to Intelligence category in `LINKEDOUT_HELP_TEXT` |
| `backend/src/linkedout/commands/import_connections.py` | 3 | Update next steps to recommend enrichment first |
| `docs/specs/cli_commands.collab.md` | 4 | Add `enrich` command spec |

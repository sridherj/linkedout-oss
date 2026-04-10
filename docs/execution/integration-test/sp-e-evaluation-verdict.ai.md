# SP-E: Evaluation & Verdict

**Phase:** Integration Test for Installation
**Plan tasks:** E1 (verdict data structures), E2 (hard gate vs advisory), E3 (verdict output)
**Dependencies:** SP-D (parent harness produces phase results that feed into verdict)
**Blocks:** —
**Can run in parallel with:** SP-F (burnish mode)

## Objective

Define the verdict data structures, implement the two-layer assertion system (structural hard gate + qualitative advisory), and produce a structured JSON verdict file. The verdict module is called by the parent harness (SP-D) after all phases complete (or after a phase fails).

## Context

- Read shared context: `docs/execution/integration-test/_shared_context.md`
- Read plan (Sub-phase E section): `docs/plan/integration-test-installation.md`
- Read requirements (Scenario 6 — evaluation): `.taskos/integration_test_refined_requirements.collab.md`
- Read plan review (Section 3 — assertions): `.taskos/docs/plan-review-integration-test.md`

## Deliverables

### E1. Verdict data structures

**File to create:** `backend/src/dev_tools/verdict.py`

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PhaseVerdict:
    phase: str             # "I", "II", "III"
    passed: bool           # based on structural assertions ONLY
    errors: list[str]      # specific error messages
    warnings: list[str]    # non-blocking issues
    duration_seconds: float

@dataclass
class UXQualityScore:
    overall: int               # 1-10 (advisory, NOT a gate)
    clarity: int               # 1-10
    information_density: int   # 1-10
    options_quality: int       # 1-10
    error_recovery: int        # 1-10
    polish: int                # 1-10
    reasoning: str             # detailed reasoning for the scores
    prompt_improvements: list[str]  # specific suggestions for skill prompt changes

@dataclass
class TestVerdict:
    timestamp: str              # ISO 8601
    mode: str                   # "burnish" or "regression"
    phases: list[PhaseVerdict]
    ux_quality: Optional[UXQualityScore]  # advisory, may be None if phases failed early
    overall_passed: bool        # based ONLY on structural assertions
    session_log_path: str
    decision_log_path: Optional[str]  # burnish mode only

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""

    def render_summary(self) -> str:
        """Render a human-readable summary for stdout."""
```

### E2. Hard gate (structural) vs advisory (qualitative)

The verdict module implements two evaluation layers:

**Hard gate (determines `overall_passed`):**
- Zero tracebacks across all phases
- Zero unexpected sudo prompts
- Zero stalls >120s (setup) or >60s (queries)
- All queries return >= 1 result
- All results have non-null `name`, `company`, `title`
- Phase II: `affinity_score` present, enriched fields populated
- Readiness report shows zero gaps

```python
def evaluate_structural(phase_results: list[dict]) -> list[PhaseVerdict]:
    """Apply structural assertions to phase results.
    Returns PhaseVerdict per phase with pass/fail."""
```

**Advisory (feeds into prompt improvements, NOT a gate):**
- UX quality score 1-10 per dimension
- Specific prompt improvement suggestions
- "Would I be proud to ship this?" reasoning
- Perspective: product solutioning expert at Apple

```python
def evaluate_quality(session_output: str) -> UXQualityScore:
    """LLM-based qualitative evaluation of the session output.
    Returns advisory UX quality scores and prompt improvement suggestions.
    This is called by the parent Claude — it uses its own judgment to score."""
```

Note: `evaluate_quality()` is not a traditional function — it's a structured prompt for the parent Claude to follow when evaluating output quality. The parent Claude reads the session output and fills in the `UXQualityScore` fields based on its assessment. The function signature documents the interface.

### E3. Verdict output

**Location:** `/tmp/linkedout-oss/verdict-YYYYMMDD-HHMMSS.json`

```python
def write_verdict(verdict: TestVerdict) -> Path:
    """Write verdict to JSON file and return the path.
    Also prints summary to stdout."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = Path(f"/tmp/linkedout-oss/verdict-{timestamp}.json")
    path.write_text(json.dumps(verdict.to_dict(), indent=2))
    print(verdict.render_summary())
    return path
```

**Rendered summary format** (printed to stdout):

```
========================================
Integration Test Verdict
========================================
Mode: burnish
Timestamp: 2026-04-10T12:34:56Z

Phase I (Demo):     PASS  (45.2s)
Phase II (Full):    PASS  (312.8s)
Phase III (Verify): PASS  (28.4s)

Overall: PASS

UX Quality (advisory):
  Overall:              8/10
  Clarity:              9/10
  Information density:  7/10
  Options quality:      8/10
  Error recovery:       6/10
  Polish:               8/10

Prompt improvements:
  - Reduce verbosity in seed data import progress output
  - Add time estimates for enrichment step

Verdict: /tmp/linkedout-oss/verdict-20260410-123456.json
Session: /tmp/linkedout-oss/session-20260410-120000.log
========================================
```

## Verification

1. `PhaseVerdict`, `UXQualityScore`, `TestVerdict` can be instantiated with valid data
2. `TestVerdict.to_dict()` produces valid JSON (round-trips through `json.dumps`/`json.loads`)
3. `TestVerdict.render_summary()` produces human-readable text with all fields
4. `write_verdict()` creates a JSON file at the expected path
5. A verdict with `overall_passed=False` correctly reflects when any phase has `passed=False`
6. `evaluate_structural()` correctly fails when:
   - A traceback is detected
   - A query returns 0 results
   - A result has a null `name` field
   - Readiness report has gaps

## Notes

- Keep this module focused on data structures and serialization. The actual evaluation logic is simple — structural assertions are boolean checks, qualitative evaluation is done by the parent Claude.
- `evaluate_quality()` is essentially a structured prompt/template for the parent Claude to follow. It doesn't make API calls — the parent Claude IS the LLM doing the evaluation.
- The verdict file path uses local time, not UTC, for human readability.
- This module has no dependencies on SP-B or SP-C — it only depends on the data structures from SP-D (which it helps define).

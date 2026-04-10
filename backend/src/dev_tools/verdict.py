# SPDX-License-Identifier: Apache-2.0
"""Evaluation framework and verdict rendering for the integration test.

Provides the two-layer assertion system:
  - Structural hard gate: boolean checks that determine pass/fail
  - Qualitative advisory: UX quality scoring (prompt template for parent Claude)

Called by integration_test.py after phases complete. This module owns
evaluation logic and verdict serialization; the harness owns test execution.

Usage (from integration_test.py):
    from dev_tools.verdict import evaluate_structural, write_verdict, FullVerdict

    phase_verdicts = evaluate_structural(phase_results, log_errors)
    verdict = FullVerdict.from_results(mode, phase_verdicts, session_log_path)
    path = write_verdict(verdict)
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

VERDICT_DIR = Path("/tmp/linkedout-oss")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PhaseVerdict:
    """Evaluated result for a single test phase.

    Produced by evaluate_structural() from raw PhaseResult data + log errors.
    """

    phase: str  # "demo", "full", "verify"
    passed: bool  # based on structural assertions ONLY
    errors: list[str] = field(default_factory=list)  # blocking issues
    warnings: list[str] = field(default_factory=list)  # non-blocking issues
    duration_seconds: float = 0.0


@dataclass
class UXQualityScore:
    """Advisory UX quality assessment (NOT a gate).

    Filled in by the parent Claude using the quality_evaluation_prompt() rubric.
    """

    overall: int = 0  # 1-10
    clarity: int = 0  # 1-10
    information_density: int = 0  # 1-10
    options_quality: int = 0  # 1-10
    error_recovery: int = 0  # 1-10
    polish: int = 0  # 1-10
    reasoning: str = ""
    prompt_improvements: list[str] = field(default_factory=list)


@dataclass
class FullVerdict:
    """Complete verdict combining structural evaluation + advisory quality.

    Complements TestVerdict in integration_test.py — this is the rich,
    serializable version written to the timestamped verdict JSON file.
    """

    timestamp: str  # ISO 8601
    mode: str  # "burnish" or "regression"
    phases: list[PhaseVerdict] = field(default_factory=list)
    ux_quality: Optional[UXQualityScore] = None
    overall_passed: bool = False
    session_log_path: str = ""
    decision_log_path: Optional[str] = None  # burnish mode only
    burnish_fixes: int = 0

    @classmethod
    def from_results(
        cls,
        mode: str,
        phase_verdicts: list[PhaseVerdict],
        session_log_path: str = "",
        decision_log_path: str | None = None,
        burnish_fixes: int = 0,
        ux_quality: UXQualityScore | None = None,
    ) -> FullVerdict:
        """Build a FullVerdict from evaluated phase verdicts."""
        overall = all(pv.passed for pv in phase_verdicts) and len(phase_verdicts) > 0
        return cls(
            timestamp=datetime.now().astimezone().isoformat(),
            mode=mode,
            phases=phase_verdicts,
            ux_quality=ux_quality,
            overall_passed=overall,
            session_log_path=session_log_path,
            decision_log_path=decision_log_path,
            burnish_fixes=burnish_fixes,
        )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON output."""
        return asdict(self)

    def render_summary(self) -> str:
        """Render a human-readable summary for stdout."""
        lines = [
            "========================================",
            "Integration Test Verdict",
            "========================================",
            f"Mode: {self.mode}",
            f"Timestamp: {self.timestamp}",
            "",
        ]

        phase_labels = {"demo": "Phase I (Demo)", "full": "Phase II (Full)", "verify": "Phase III (Verify)"}
        for pv in self.phases:
            label = phase_labels.get(pv.phase, pv.phase)
            status = "PASS" if pv.passed else "FAIL"
            lines.append(f"  {label + ':':<22} {status}  ({pv.duration_seconds:.1f}s)")
            for err in pv.errors:
                lines.append(f"    ERROR: {err}")
            for warn in pv.warnings:
                lines.append(f"    WARN:  {warn}")

        lines.append("")
        lines.append(f"Overall: {'PASS' if self.overall_passed else 'FAIL'}")

        if self.burnish_fixes:
            lines.append(f"Burnish fixes applied: {self.burnish_fixes}")

        if self.ux_quality:
            q = self.ux_quality
            lines.extend([
                "",
                "UX Quality (advisory):",
                f"  Overall:              {q.overall}/10",
                f"  Clarity:              {q.clarity}/10",
                f"  Information density:  {q.information_density}/10",
                f"  Options quality:      {q.options_quality}/10",
                f"  Error recovery:       {q.error_recovery}/10",
                f"  Polish:               {q.polish}/10",
            ])
            if q.prompt_improvements:
                lines.append("")
                lines.append("Prompt improvements:")
                for imp in q.prompt_improvements:
                    lines.append(f"  - {imp}")

        lines.extend([
            "",
            f"Verdict: {self.session_log_path}",
            "========================================",
        ])
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Structural evaluation (hard gate)
# ---------------------------------------------------------------------------

# Error types from log_reader.detect_errors() that are hard failures
_HARD_FAIL_ERROR_TYPES = {"python_traceback", "unexpected_sudo", "setup_failure"}


def evaluate_structural(
    phase_results: dict[str, dict],
    log_errors: list[dict],
) -> list[PhaseVerdict]:
    """Apply structural assertions to phase results.

    Args:
        phase_results: Dict of phase name -> PhaseResult as dict
            (keys: status, errors, duration_s). From integration_test.py.
        log_errors: Output of SessionLogReader.detect_errors().
            Each dict has keys: type, line.

    Returns:
        List of PhaseVerdict, one per phase that was executed.
    """
    # Categorize log errors by severity
    hard_errors = [e for e in log_errors if e["type"] in _HARD_FAIL_ERROR_TYPES]
    soft_errors = [e for e in log_errors if e["type"] not in _HARD_FAIL_ERROR_TYPES]

    verdicts: list[PhaseVerdict] = []

    for phase_name, result in phase_results.items():
        errors: list[str] = []
        warnings: list[str] = []

        # Carry forward errors from the phase harness
        for err in result.get("errors", []):
            errors.append(err)

        # Phase-level status from harness
        if result.get("status") == "fail" and not errors:
            errors.append(f"Phase {phase_name} reported failure")

        passed = result.get("status") == "pass" and len(errors) == 0
        verdicts.append(PhaseVerdict(
            phase=phase_name,
            passed=passed,
            errors=errors,
            warnings=warnings,
            duration_seconds=result.get("duration_s", 0.0),
        ))

    # Apply log-level hard errors to the last phase (they span the session)
    if verdicts and hard_errors:
        last = verdicts[-1]
        for err in hard_errors:
            msg = f"[{err['type']}] {err['line'][:120]}"
            last.errors.append(msg)
        last.passed = False

    # Soft errors become warnings on the last phase
    if verdicts and soft_errors:
        last = verdicts[-1]
        for err in soft_errors:
            last.warnings.append(f"[{err['type']}] {err['line'][:120]}")

    return verdicts


# ---------------------------------------------------------------------------
# Qualitative evaluation (advisory, NOT a gate)
# ---------------------------------------------------------------------------

_QUALITY_RUBRIC = """\
You are a product solutioning expert at Apple evaluating the user experience
of the LinkedOut setup and query flow. Review the session output below and
score each dimension 1-10.

## Dimensions

1. **Clarity** — Is each step's purpose and progress obvious? Are errors explained?
2. **Information density** — Does the output show useful detail without noise?
3. **Options quality** — Are prompts well-worded with sensible defaults?
4. **Error recovery** — When something fails, is the recovery path clear?
5. **Polish** — Formatting, timing, lack of glitches. Would you ship this?

## Output format

Return a JSON object matching this exact structure (no markdown fencing):
{
    "overall": <1-10>,
    "clarity": <1-10>,
    "information_density": <1-10>,
    "options_quality": <1-10>,
    "error_recovery": <1-10>,
    "polish": <1-10>,
    "reasoning": "<2-3 sentences explaining overall impression>",
    "prompt_improvements": ["<specific improvement 1>", "<specific improvement 2>"]
}

## Session output to evaluate

"""


def quality_evaluation_prompt(session_output: str) -> str:
    """Return the structured prompt for parent Claude to evaluate UX quality.

    The parent Claude reads this prompt, reviews the session output,
    and fills in UXQualityScore fields based on its assessment.
    This function does NOT call an LLM — the parent Claude IS the evaluator.
    """
    return _QUALITY_RUBRIC + session_output


def parse_quality_response(response_json: str) -> UXQualityScore:
    """Parse parent Claude's quality evaluation response into a UXQualityScore.

    Args:
        response_json: JSON string matching the UXQualityScore structure.

    Returns:
        UXQualityScore populated from the response.
    """
    data = json.loads(response_json)
    return UXQualityScore(
        overall=int(data.get("overall", 0)),
        clarity=int(data.get("clarity", 0)),
        information_density=int(data.get("information_density", 0)),
        options_quality=int(data.get("options_quality", 0)),
        error_recovery=int(data.get("error_recovery", 0)),
        polish=int(data.get("polish", 0)),
        reasoning=str(data.get("reasoning", "")),
        prompt_improvements=list(data.get("prompt_improvements", [])),
    )


# ---------------------------------------------------------------------------
# Verdict output
# ---------------------------------------------------------------------------


def write_verdict(verdict: FullVerdict) -> Path:
    """Write verdict to a timestamped JSON file and print summary to stdout.

    Returns the path to the written file.
    """
    VERDICT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = VERDICT_DIR / f"verdict-{timestamp}.json"
    path.write_text(json.dumps(verdict.to_dict(), indent=2))

    summary = verdict.render_summary()
    print(summary)  # noqa: T201 — intentional stdout for human consumption
    logger.info("Verdict written to {}", path)

    return path

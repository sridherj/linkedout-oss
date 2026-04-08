# SPDX-License-Identifier: Apache-2.0
"""Multi-turn conversation replay PoC -- validates conversational search with ConversationManager.

Tests a 5-turn conversation (search -> refine -> explain -> re-query -> aggregate)
to measure context coherence and token usage across turns.

Run with: pytest tests/eval/test_multiturn_poc.py -m eval -v -s
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from tests.eval.multi_turn_runner import ConversationRunResult, MultiTurnRunner

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.eval

# --- 5-Turn Conversation Scenario ---
# Turn 4 and 5 changed: LLM re-queries with criteria instead of using removed tools.
CONVERSATION_QUERIES = [
    # Turn 1: Search — complex career pattern query
    "Find people who started in IT services but have been climbing fast at product companies — senior+ in under 3 years",
    # Turn 2: Refine — filter on top of complex results
    "Of those, only show ones who are in Bangalore or have worked there recently",
    # Turn 3: Explain — requires memory of criteria from turn 1
    "Why did the first person in the results make the cut? What's their trajectory?",
    # Turn 4: Re-query with exclusion — LLM re-queries with exclusion in SQL WHERE clause
    "Show me only people NOT at big tech companies like Google, Meta, Amazon — I only want people who've fully transitioned to startups",
    # Turn 5: SQL aggregation — LLM runs GROUP BY query
    "What companies are the remaining people at? Break it down by company",
]

OUTPUT_DIR = Path(__file__).parent.parent.parent / "benchmarks" / "multiturn_poc"


def _write_yaml_report(results: dict, path: Path) -> None:
    """Write structured YAML report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(results, f, default_flow_style=False, sort_keys=False, width=120)


def _write_markdown_report(result: ConversationRunResult, path: Path) -> None:
    """Write human-readable markdown report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Multi-Turn Conversation PoC Report",
        f"\n**Generated:** {datetime.now().isoformat()}",
        f"\n**Queries:** {len(CONVERSATION_QUERIES)} turns",
        "",
        "| Turn | Query (truncated) | Input Tokens | Output Tokens | Results | Latency (ms) | Query Type |",
        "|------|-------------------|-------------|---------------|---------|-------------|------------|",
    ]
    for t in result.turns:
        lines.append(
            f"| {t.turn_number} | {t.query[:50]}... | "
            f"{t.input_token_estimate:,} | {t.output_token_estimate:,} | "
            f"{t.result_count} | {t.latency_ms:,.0f} | {t.query_type} |"
        )
    lines.append(f"\n**Total input tokens:** {result.total_input_tokens:,}")
    lines.append(f"**Total output tokens:** {result.total_output_tokens:,}")

    # Per-turn answers
    lines.append("\n### Turn Answers\n")
    for t in result.turns:
        lines.append(f"**Turn {t.turn_number}** ({t.query[:60]}...):\n")
        lines.append(f"> {t.answer_snippet}\n")

    path.write_text("\n".join(lines))


@pytest.fixture(scope="module")
def runner(db_session, app_user_id):
    """Create a MultiTurnRunner for the conversation PoC."""
    return MultiTurnRunner(session=db_session, app_user_id=app_user_id)


class TestMultiTurnConversation:
    """Run the 5-turn conversation and verify coherence."""

    def test_conversation_via_conversation_manager(self, runner):
        """All 5 turns should complete with non-empty results using ConversationManager."""
        result = runner.run_conversation(queries=CONVERSATION_QUERIES)
        self._assert_basic_coherence(result)
        return result

    def test_full_run_and_report(self, runner):
        """Run the full conversation and produce a report."""
        result = runner.run_conversation(queries=CONVERSATION_QUERIES)

        # Write reports
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        yaml_data = {
            "total_input_tokens": result.total_input_tokens,
            "total_output_tokens": result.total_output_tokens,
            "errors": result.errors,
            "turns": [asdict(t) for t in result.turns],
        }
        _write_yaml_report(yaml_data, OUTPUT_DIR / f"results_{timestamp}.yaml")
        _write_markdown_report(result, OUTPUT_DIR / f"report_{timestamp}.md")

        logger.info(f"\nReports written to {OUTPUT_DIR}")

        assert len(result.turns) == len(CONVERSATION_QUERIES), (
            f"Only completed {len(result.turns)}/{len(CONVERSATION_QUERIES)} turns"
        )

    def _assert_basic_coherence(self, result: ConversationRunResult) -> None:
        """Basic coherence checks."""
        # All turns should complete without errors
        assert not result.errors, f"Had errors: {result.errors}"
        assert len(result.turns) == len(CONVERSATION_QUERIES), (
            f"Only completed {len(result.turns)}/{len(CONVERSATION_QUERIES)} turns"
        )

        # Turn 5 (aggregate) should produce an answer, not just results
        turn5 = result.turns[4]
        assert turn5.answer_snippet and len(turn5.answer_snippet.strip()) > 10, (
            "Turn 5 (aggregate) returned empty/trivial answer"
        )

        # Token usage should grow across turns (more context = more input tokens)
        if len(result.turns) >= 2:
            assert result.turns[1].input_token_estimate >= result.turns[0].input_token_estimate, (
                f"Turn 2 input tokens ({result.turns[1].input_token_estimate}) "
                f"should be >= Turn 1 ({result.turns[0].input_token_estimate})"
            )

        # Log key metrics for manual review
        logger.info("\n--- Conversation Results ---")
        for t in result.turns:
            logger.info(
                f"  Turn {t.turn_number}: {t.input_token_estimate:>6} in / "
                f"{t.output_token_estimate:>6} out / {t.result_count:>3} results / "
                f"{t.latency_ms:>8.0f}ms / {t.query_type}"
            )
            logger.info(f"    Answer: {t.answer_snippet[:150]}...")

# SPDX-License-Identifier: Apache-2.0
"""Multi-turn conversation runner for testing conversational search replay.

Orchestrates a sequence of search turns through SearchAgent, managing
conversation history via ConversationManager and search_turn rows.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from linkedout.intelligence.agents.search_agent import SearchAgent

logger = logging.getLogger(__name__)


@dataclass
class TurnMetrics:
    """Metrics for a single conversation turn."""
    turn_number: int
    query: str
    input_token_estimate: int
    output_token_estimate: int
    result_count: int
    query_type: str
    answer_snippet: str  # First 300 chars of the answer
    latency_ms: float
    transcript_message_count: int


@dataclass
class ConversationRunResult:
    """Full result of a multi-turn conversation run."""
    turns: list[TurnMetrics] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    errors: list[str] = field(default_factory=list)


class MultiTurnRunner:
    """Orchestrates multi-turn conversations through SearchAgent.

    Manages turn history between turns using ConversationManager.
    Each turn's transcript is stored as a turn dict for the next turn.
    """

    def __init__(self, session: Session, app_user_id: str):
        self._session = session
        self._app_user_id = app_user_id

    def run_conversation(
        self,
        queries: list[str],
    ) -> ConversationRunResult:
        """Run a sequence of queries as a multi-turn conversation.

        Args:
            queries: List of user queries in order.
        """
        result = ConversationRunResult()

        # Accumulated turn history (list of turn dicts for ConversationManager)
        turn_history: list[dict[str, Any]] = []
        agent = SearchAgent(session=self._session, app_user_id=self._app_user_id)

        for turn_num, query in enumerate(queries, 1):
            try:
                start_ns = time.perf_counter_ns()
                turn_response = agent.run_turn(
                    query=query,
                    turn_history=turn_history if turn_history else None,
                    limit=20,
                )
                latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)

                # Capture metrics
                metrics = TurnMetrics(
                    turn_number=turn_num,
                    query=query,
                    input_token_estimate=turn_response.input_token_estimate,
                    output_token_estimate=turn_response.output_token_estimate,
                    result_count=len(turn_response.results),
                    query_type=turn_response.query_type,
                    answer_snippet=turn_response.message[:300],
                    latency_ms=latency_ms,
                    transcript_message_count=len(turn_response.turn_transcript),
                )
                result.turns.append(metrics)
                result.total_input_tokens += turn_response.input_token_estimate
                result.total_output_tokens += turn_response.output_token_estimate

                # Add this turn to history for future turns
                turn_history.append({
                    "user_query": query,
                    "transcript": turn_response.turn_transcript,
                    "summary": None,
                })

                logger.info(
                    f"Turn {turn_num}: "
                    f"{len(turn_response.results)} results, "
                    f"~{turn_response.input_token_estimate} input tokens, "
                    f"{latency_ms}ms"
                )

            except Exception as e:
                logger.exception(f"Turn {turn_num} failed: {e}")
                result.errors.append(f"Turn {turn_num}: {e}")

        return result

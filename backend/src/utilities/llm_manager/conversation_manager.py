# SPDX-License-Identifier: Apache-2.0
"""ConversationManager -- builds conversation history from turn rows.

Recent N turns are kept verbatim; older turns are summarized via LLM.
The caller provides a summarization prompt. LLMClient stays untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utilities.llm_manager.llm_client import LLMClient
from utilities.llm_manager.llm_message import LLMMessage
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")


@dataclass
class SummaryResult:
    """Result of build_history -- messages plus any newly generated summaries."""

    messages: list[dict[str, Any]]
    generated_summaries: dict[int, str] = field(default_factory=dict)
    """Map of turn index (in the input list) -> generated summary text.
    Caller is responsible for caching these back to DB."""


class ConversationManager:
    """Build conversation history from turn rows with smart summarization.

    Recent turns are kept verbatim as user/assistant message pairs.
    Older turns are collapsed into a single summary message. If a turn
    already has a cached summary, it is reused; otherwise the LLM
    generates one.

    Args:
        llm_client: An LLMClient instance for generating summaries.
        summarization_prompt: Domain-specific prompt text for summarization.
        recent_turns: Number of most-recent turns to keep verbatim.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        summarization_prompt: str,
        recent_turns: int = 4,
    ):
        self._llm_client = llm_client
        self._summarization_prompt = summarization_prompt
        self._recent_turns = recent_turns

    def build_history(self, turns: list[dict[str, Any]]) -> SummaryResult:
        """Build message history from turn rows.

        Args:
            turns: Turn rows from DB ordered by turn_number. Each dict
                must have at least ``user_query`` (str). Optional keys:
                ``transcript`` (list of message dicts), ``summary`` (str|None).

        Returns:
            SummaryResult with messages ready to inject into LLMMessage,
            plus any newly generated summaries keyed by turn index.
        """
        if len(turns) <= self._recent_turns:
            return SummaryResult(messages=self._turns_to_messages(turns))

        older = turns[: -self._recent_turns]
        recent = turns[-self._recent_turns :]

        summary_text, generated = self._summarize_older_turns(older)

        messages: list[dict[str, Any]] = []
        if summary_text:
            messages.append({
                "role": "assistant",
                "content": f"[Previous conversation summary]\n{summary_text}",
            })

        messages.extend(self._turns_to_messages(recent))
        return SummaryResult(messages=messages, generated_summaries=generated)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _summarize_older_turns(
        self, older_turns: list[dict[str, Any]]
    ) -> tuple[str, dict[int, str]]:
        """Produce a combined summary for older turns.

        Returns (combined_summary_text, {turn_index: generated_summary}).
        """
        cached_parts: list[str] = []
        uncached_turns: list[tuple[int, dict[str, Any]]] = []

        for idx, turn in enumerate(older_turns):
            if turn.get("summary"):
                cached_parts.append(turn["summary"])
            else:
                uncached_turns.append((idx, turn))

        generated: dict[int, str] = {}

        if uncached_turns:
            # Build a text block from uncached turns for batch summarization
            turn_texts = []
            for _, turn in uncached_turns:
                turn_texts.append(f"User: {turn['user_query']}")
                if turn.get("transcript"):
                    for msg in turn["transcript"]:
                        role = msg.get("role", "")
                        content = msg.get("content", "")
                        if role == "assistant" and content:
                            turn_texts.append(f"Assistant: {content}")

            conversation_block = "\n".join(turn_texts)

            msg = LLMMessage()
            msg.add_system_message(self._summarization_prompt)
            msg.add_user_message(conversation_block)

            try:
                summary = self._llm_client.call_llm(msg)
            except Exception:
                logger.exception("Failed to generate conversation summary")
                # Fallback: use raw user queries as summary
                summary = " | ".join(
                    t["user_query"] for _, t in uncached_turns
                )

            # Store the generated summary for each uncached turn
            for idx, _ in uncached_turns:
                generated[idx] = summary

            cached_parts.append(summary)

        return "\n\n".join(cached_parts), generated

    @staticmethod
    def _turns_to_messages(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert turn rows into user/assistant message pairs."""
        messages: list[dict[str, Any]] = []
        for turn in turns:
            messages.append({"role": "user", "content": turn["user_query"]})
            # If transcript has assistant messages, include the last one
            if turn.get("transcript"):
                for msg in reversed(turn["transcript"]):
                    if msg.get("role") == "assistant" and msg.get("content"):
                        messages.append({
                            "role": "assistant",
                            "content": msg["content"],
                        })
                        break
        return messages

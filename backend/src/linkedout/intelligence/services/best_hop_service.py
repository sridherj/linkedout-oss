# SPDX-License-Identifier: Apache-2.0
"""BestHopService -- pre-assemble context, call LLM once, rank mutual connections."""
from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from linkedout.intelligence.contracts import BestHopRequest, BestHopResultItem
from shared.config import get_config
from shared.utils.linkedin_url import normalize_linkedin_url
from utilities.llm_manager import LLMFactory, LLMMessage, SystemUser
from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

MAX_MUTUALS_FOR_EXPERIENCE = 50

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "best_hop_ranking.md"


# ── Helper dataclasses ────────────────────────────────────────────────


@dataclass
class BestHopContext:
    target_profile: dict
    target_experience: list[dict]
    target_connection: dict | None
    mutuals: list[dict]
    mutual_experience: dict[str, list[dict]]
    matched_count: int
    unmatched_count: int
    unmatched_urls: list[str]


@dataclass
class BestHopDone:
    total: int
    matched: int
    unmatched: int
    unmatched_urls: list[str] = field(default_factory=list)


# ── Service ───────────────────────────────────────────────────────────


class BestHopService:
    def __init__(self, session: Session, app_user_id: str):
        self.session = session
        self.app_user_id = app_user_id
        self._model_name = get_config().llm.search_model

    # ── Data assembly ─────────────────────────────────────────────────

    def assemble_context(self, request: BestHopRequest) -> BestHopContext:
        """Run batch SQL queries to pre-assemble all data the LLM needs."""

        # Normalize URLs — extension may send trailing slashes, country prefixes, etc.
        target_url = normalize_linkedin_url(request.target_url) or request.target_url
        mutual_urls = [normalize_linkedin_url(u) or u for u in request.mutual_urls]

        # Query 3 — Target profile
        target_row = self.session.execute(
            text(
                "SELECT cp.id, cp.full_name, cp.headline, cp.current_position, "
                "cp.current_company_name, cp.location_city, cp.seniority_level, cp.about "
                "FROM crawled_profile cp "
                "WHERE cp.linkedin_url = :target_url "
                "LIMIT 1"
            ),
            {"target_url": target_url},
        ).mappings().first()

        if not target_row:
            raise ValueError(
                f"Target profile not found in DB for URL: {target_url}. "
                "The target must be enriched before best-hop triggers."
            )

        target_profile = dict(target_row)
        target_profile_id = target_profile["id"]

        # Query 4 — Target experience
        target_exp_rows = self.session.execute(
            text(
                "SELECT e.company_name, e.company_id, e.position, e.start_date, "
                "e.end_date, e.is_current, e.seniority_level "
                "FROM experience e "
                "WHERE e.crawled_profile_id = :target_profile_id "
                "ORDER BY e.start_date DESC"
            ),
            {"target_profile_id": target_profile_id},
        ).mappings().all()
        target_experience = [dict(r) for r in target_exp_rows]

        # Query 5 — Target connection status (is target a direct connection?)
        target_conn_row = self.session.execute(
            text(
                "SELECT c.affinity_score, c.dunbar_tier "
                "FROM connection c WHERE c.crawled_profile_id = :target_profile_id "
                "LIMIT 1"
            ),
            {"target_profile_id": target_profile_id},
        ).mappings().first()
        target_connection = dict(target_conn_row) if target_conn_row else None

        # Query 1 — Mutual connections (batch lookup by URL)
        mutual_rows = self.session.execute(
            text(
                "SELECT cp.id, cp.full_name, cp.headline, cp.current_position, "
                "cp.current_company_name, cp.linkedin_url, cp.location_city, "
                "cp.seniority_level, cp.about, "
                "c.id AS connection_id, c.affinity_score, c.dunbar_tier, "
                "c.affinity_career_overlap, c.affinity_external_contact, "
                "c.affinity_recency, c.connected_at "
                "FROM crawled_profile cp "
                "JOIN connection c ON c.crawled_profile_id = cp.id "
                "WHERE cp.linkedin_url = ANY(:mutual_urls) "
                "ORDER BY c.affinity_score DESC NULLS LAST"
            ),
            {"mutual_urls": mutual_urls},
        ).mappings().all()
        mutuals = [dict(r) for r in mutual_rows]

        # Compute unmatched URLs — normalize DB URLs too for consistent comparison
        matched_urls = {normalize_linkedin_url(m["linkedin_url"]) or m["linkedin_url"] for m in mutuals}
        unmatched_urls = [u for u in mutual_urls if u not in matched_urls]

        # Query 2 — Experience for top 50 mutuals by affinity
        top_50_ids = [m["id"] for m in mutuals[:MAX_MUTUALS_FOR_EXPERIENCE]]
        mutual_experience: dict[str, list[dict]] = {}
        if top_50_ids:
            exp_rows = self.session.execute(
                text(
                    "SELECT e.crawled_profile_id, e.company_name, e.company_id, e.position, "
                    "e.start_date, e.end_date, e.is_current, e.seniority_level "
                    "FROM experience e "
                    "WHERE e.crawled_profile_id = ANY(:top_50_profile_ids) "
                    "ORDER BY e.crawled_profile_id, e.start_date DESC"
                ),
                {"top_50_profile_ids": top_50_ids},
            ).mappings().all()
            for row in exp_rows:
                r = dict(row)
                pid = r.pop("crawled_profile_id")
                mutual_experience.setdefault(pid, []).append(r)

        return BestHopContext(
            target_profile=target_profile,
            target_experience=target_experience,
            target_connection=target_connection,
            mutuals=mutuals,
            mutual_experience=mutual_experience,
            matched_count=len(mutuals),
            unmatched_count=len(unmatched_urls),
            unmatched_urls=unmatched_urls,
        )

    # ── Prompt building ───────────────────────────────────────────────

    def build_prompt(self, context: BestHopContext) -> str:
        """Build the system prompt with injected context."""
        # Load template if it exists, otherwise use inline fallback
        template = ""
        if _PROMPT_PATH.exists():
            template = _PROMPT_PATH.read_text()

        # Build context sections
        sections: list[str] = []

        # Target section
        tp = context.target_profile
        target_lines = [
            "## Target",
            f"Name: {tp.get('full_name', 'Unknown')}",
            f"Position: {tp.get('current_position', 'N/A')} at {tp.get('current_company_name', 'N/A')}",
            f"Headline: {tp.get('headline', 'N/A')}",
            f"Location: {tp.get('location_city', 'N/A')}",
            f"Seniority: {tp.get('seniority_level', 'N/A')}",
        ]
        if tp.get("about"):
            target_lines.append(f"About: {tp['about'][:500]}")

        if context.target_experience:
            target_lines.append("\nExperience:")
            for exp in context.target_experience[:10]:
                current = " (current)" if exp.get("is_current") else ""
                dates = f"{exp.get('start_date', '?')} – {exp.get('end_date', 'present')}"
                target_lines.append(f"  - {exp.get('position', '?')} at {exp.get('company_name', '?')} ({dates}){current}")

        if context.target_connection:
            tc = context.target_connection
            target_lines.append(f"\nDirect connection: Yes (affinity: {tc.get('affinity_score', 'N/A')}, tier: {tc.get('dunbar_tier', 'N/A')})")
        else:
            target_lines.append("\nDirect connection: No")

        sections.append("\n".join(target_lines))

        # Mutuals section
        mutual_lines = [
            f"\n## Your Mutual Connections ({context.matched_count} found in DB, "
            f"{context.unmatched_count} not yet enriched, ordered by affinity)"
        ]
        for i, m in enumerate(context.mutuals, 1):
            affinity = m.get("affinity_score", "N/A")
            tier = m.get("dunbar_tier", "N/A")
            mutual_lines.append(f"\n### {i}. {m.get('full_name', 'Unknown')} (affinity: {affinity}, tier: {tier})")
            mutual_lines.append(f"crawled_profile_id: {m['id']}")
            mutual_lines.append(f"Position: {m.get('current_position', 'N/A')} at {m.get('current_company_name', 'N/A')}")
            if m.get("headline"):
                mutual_lines.append(f"Headline: {m['headline']}")
            if m.get("location_city"):
                mutual_lines.append(f"Location: {m['location_city']}")

            # Add experience if available
            pid = m["id"]
            exps = context.mutual_experience.get(pid, [])
            if exps:
                mutual_lines.append("Experience:")
                for exp in exps[:5]:
                    current = " (current)" if exp.get("is_current") else ""
                    mutual_lines.append(
                        f"  - {exp.get('position', '?')} at {exp.get('company_name', '?')}{current}"
                    )

        sections.append("\n".join(mutual_lines))

        context_text = "\n\n".join(sections)

        if template:
            # If template has a {context} placeholder, inject; otherwise append
            if "{context}" in template:
                return template.replace("{context}", context_text)
            return template + "\n\n" + context_text

        # Inline fallback prompt
        return (
            "You are a LinkedIn networking assistant. Your task is to rank mutual connections "
            "as potential introducers to the target person.\n\n"
            "For each mutual, consider:\n"
            "1. How well the user knows this mutual (affinity score, dunbar tier)\n"
            "2. How likely this mutual knows the target (shared companies, similar roles, same location)\n"
            "3. The quality of introduction this mutual could provide\n\n"
            "Return a JSON array of ranked results. Each item must have:\n"
            "- crawled_profile_id: string\n"
            "- rank: integer (1 = best)\n"
            "- why_this_person: string (1-2 sentences explaining why they're a good connector)\n\n"
            "Return ONLY the JSON array, no other text.\n\n"
            + context_text
        )

    # ── LLM ranking ───────────────────────────────────────────────────

    def _create_llm_client(self):
        settings = get_config()
        api_key = settings.openai_api_key or settings.llm_api_key
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name=self._model_name,
            api_key=api_key,
            temperature=0,
        )
        return LLMFactory.create_client(SystemUser("best-hop-service"), config)

    def rank(self, request: BestHopRequest) -> Generator[BestHopResultItem | BestHopDone, None, None]:
        """Assemble context, call LLM, merge results.

        Yields BestHopResultItem for each ranked candidate.
        Yields BestHopDone as the final item with summary stats.
        """
        context = self.assemble_context(request)
        system_prompt = self.build_prompt(context)
        client = self._create_llm_client()

        msg = LLMMessage()
        msg.add_system_message(system_prompt)
        msg.add_user_message(
            f"Rank the top mutual connections for introducing me to {request.target_name}. "
            "For each, explain why they're a good connector. "
            "Return a JSON array with objects containing: crawled_profile_id, rank, why_this_person."
        )

        # Single LLM call — all context is pre-assembled in the prompt, no tools needed.
        response = client.call_llm_with_tools(msg, [])
        ranked_items = self._parse_llm_response(response.content)

        # Build lookup from mutuals for merging
        mutual_lookup = {m["id"]: m for m in context.mutuals}

        # Merge LLM rankings with SQL data and yield results
        for item in ranked_items:
            pid = item.get("crawled_profile_id", "")
            mutual = mutual_lookup.get(pid, {})
            if not mutual:
                logger.warning(f"LLM returned unknown profile ID: {pid}")
                continue

            yield BestHopResultItem(
                rank=item.get("rank", 0),
                connection_id=mutual.get("connection_id", ""),
                crawled_profile_id=pid,
                full_name=mutual.get("full_name", ""),
                current_position=mutual.get("current_position"),
                current_company_name=mutual.get("current_company_name"),
                affinity_score=mutual.get("affinity_score"),
                dunbar_tier=mutual.get("dunbar_tier"),
                linkedin_url=mutual.get("linkedin_url"),
                why_this_person=item.get("why_this_person", ""),
            )

        yield BestHopDone(
            total=len(ranked_items),
            matched=context.matched_count,
            unmatched=context.unmatched_count,
            unmatched_urls=context.unmatched_urls,
        )

    def _parse_llm_response(self, content: str) -> list[dict]:
        """Extract the JSON array from the LLM's response text."""
        content = content.strip()

        # Try to find JSON array in the response
        # Handle markdown code blocks
        if "```" in content:
            # Extract content between code fences
            parts = content.split("```")
            for part in parts[1::2]:  # odd indices are inside fences
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    parsed = json.loads(part)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    continue

        # Try direct JSON parse
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to find array brackets
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(content[start:end + 1])
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse LLM response as JSON array: {content[:200]}")
        return []

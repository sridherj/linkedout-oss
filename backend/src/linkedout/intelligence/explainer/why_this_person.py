# SPDX-License-Identifier: Apache-2.0
"""Why This Person explainer — generates 2-3 sentence explanations with highlighted attributes."""
from __future__ import annotations

import json

from shared.utilities.langfuse_guard import observe
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from linkedout.intelligence.contracts import (
    HighlightedAttribute,
    MatchStrength,
    ProfileExplanation,
    SearchResultItem,
)
from shared.config import get_config
from utilities.llm_manager import LLMFactory, LLMMessage, SystemUser
from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

BATCH_SIZE = 10

# Fixed attribute types for frontend stability
VALID_ATTRIBUTE_TYPES = {
    "skill_match", "company_match", "career_trajectory",
    "network_proximity", "tenure_signal", "seniority_match",
}

_PROMPT_TEMPLATE = """You are explaining why specific professionals from a LinkedIn network match a search query.

## Query
"{query}"

## Task
For each person below, write a concise 1-2 sentence explanation (40-50 words max) that maps specific profile attributes to the query. Help the user quickly decide if this person is worth reaching out to.

## Output Format
Return a JSON array. Each element must have exactly these fields:
```json
[
  {{
    "connection_id": "conn_abc123",
    "match_strength": "strong",
    "explanation": "1-2 concise sentences mapping profile attributes to query.",
    "highlighted_attributes": [
      {{"text": "short chip label", "color_tier": 0}}
    ]
  }}
]
```

## Rules
1. ONLY reference facts present in the data below. Never invent or assume facts.
2. Be specific: cite company names, role titles, skill names, years of experience — not generalities.
3. If the query has multiple dimensions, address each dimension explicitly.
4. match_strength: "strong" = matches most/all query dimensions, "partial" = matches some, "weak" = matches few or tangentially.
5. highlighted_attributes: pick 2-3 attributes most relevant to this specific query. Max 3 chips per profile.
6. color_tier: 0 = primary match dimension, 1 = secondary, 2 = tertiary.
7. Chip text must be short (under 25 chars) and specific (e.g. "8yr backend eng", "Flipkart → MSFT", "Series B stage").
8. If a person is a weak match, say so honestly in both match_strength and explanation.
9. Return ONLY the JSON array, no markdown fences, no extra text.

## Profiles
{formatted_profiles}"""


def _profile_key(item: SearchResultItem) -> str:
    """Return a stable unique key: connection_id if present, else crawled_profile_id."""
    return item.connection_id or item.crawled_profile_id


def _format_profile(item: SearchResultItem, enrichment: dict | None = None) -> str:
    """Format a single profile for the prompt with full context."""
    lines = [f"## Profile: {_profile_key(item)}"]
    lines.append(f"Name: {item.full_name}")

    if item.current_position and item.current_company_name:
        current = f"Current: {item.current_position} at {item.current_company_name}"
        # Add company metadata if available
        if enrichment:
            company_meta = enrichment.get("current_company_meta")
            if company_meta:
                meta_parts = []
                if company_meta.get("industry"):
                    meta_parts.append(company_meta["industry"])
                if company_meta.get("size_tier"):
                    meta_parts.append(company_meta["size_tier"])
                if meta_parts:
                    current += f" ({', '.join(meta_parts)})"
        lines.append(current)
    elif item.current_position:
        lines.append(f"Current: {item.current_position}")

    if item.headline:
        lines.append(f"Headline: {item.headline}")

    if item.location_city:
        loc = item.location_city
        if item.location_country:
            loc += f", {item.location_country}"
        lines.append(f"Location: {loc}")

    if enrichment:
        # Full career history (no truncation)
        experiences = enrichment.get("experiences", [])
        if experiences:
            career_parts = []
            for exp in experiences:
                part = f"{exp.get('position', '?')} at {exp.get('company', '?')}"
                if exp.get("company_industry") or exp.get("company_size_tier"):
                    meta = ", ".join(filter(None, [exp.get("company_industry"), exp.get("company_size_tier")]))
                    if meta:
                        part += f" ({meta})"
                if exp.get("start"):
                    part += f" [{exp['start']}"
                    part += f"–{exp['end']}" if exp.get("end") else "–present"
                    part += "]"
                career_parts.append(part)
            lines.append(f"Career: {'; '.join(career_parts)}")

        # Education
        education = enrichment.get("education", [])
        if education:
            edu_parts = []
            for edu in education:
                parts = []
                if edu.get("school"):
                    parts.append(edu["school"])
                if edu.get("degree"):
                    parts.append(edu["degree"])
                if edu.get("field"):
                    parts.append(edu["field"])
                if edu.get("end_year"):
                    parts.append(str(edu["end_year"]))
                edu_parts.append(" ".join(parts))
            lines.append(f"Education: [{', '.join(edu_parts)}]")

        # Skills
        skills = enrichment.get("skills", [])
        if skills:
            lines.append(f"Skills: [{', '.join(skills)}]")

    # Network proximity signals (from SearchResultItem directly)
    network_parts = []
    if item.affinity_score is not None:
        network_parts.append(f"Affinity={item.affinity_score:.2f}")
    if item.dunbar_tier:
        network_parts.append(f"Tier={item.dunbar_tier}")

    # Affinity sub-scores from enrichment
    if enrichment:
        affinity = enrichment.get("affinity", {})
        if affinity.get("recency"):
            network_parts.append(f"Recency={affinity['recency']:.1f}")
        if affinity.get("career_overlap"):
            network_parts.append(f"CareerOverlap={affinity['career_overlap']:.1f}")
        if affinity.get("mutual_connections"):
            network_parts.append(f"MutualConns={affinity['mutual_connections']:.1f}")

    if network_parts:
        lines.append(f"Network: {', '.join(network_parts)}")

    if item.match_context:
        match_parts = [f"{k}={v}" for k, v in item.match_context.items()]
        lines.append(f"MatchEvidence: {', '.join(match_parts)}")

    return "\n".join(lines)


def _parse_explanations(raw: str, valid_ids: set[str]) -> dict[str, ProfileExplanation]:
    """Parse structured JSON from LLM response, with text fallback."""
    # Try JSON parse first
    try:
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove opening fence (with optional language tag)
            first_newline = cleaned.index("\n")
            cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        data = json.loads(cleaned)
        if not isinstance(data, list):
            raise ValueError("Expected JSON array")

        result: dict[str, ProfileExplanation] = {}
        for entry in data:
            cid = entry.get("connection_id", "")
            if cid not in valid_ids:
                continue
            highlights = []
            for attr in entry.get("highlighted_attributes", [])[:3]:
                tier = attr.get("color_tier", 2)
                if not isinstance(tier, int) or tier < 0 or tier > 2:
                    tier = 2
                highlights.append(HighlightedAttribute(
                    text=str(attr.get("text", ""))[:25],
                    color_tier=tier,
                ))
            raw_strength = entry.get("match_strength", "partial")
            try:
                strength = MatchStrength(raw_strength)
            except ValueError:
                strength = MatchStrength.PARTIAL
            result[cid] = ProfileExplanation(
                explanation=entry.get("explanation", ""),
                match_strength=strength,
                highlighted_attributes=highlights,
            )
        return result
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("JSON parse failed for explainer output, falling back to text parse")

    # Fallback: parse "ID: explanation" text format
    import re
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\S+):\s+(.+)$", line)
        if match:
            cid, explanation = match.group(1), match.group(2)
            if cid in valid_ids:
                result[cid] = ProfileExplanation(
                    explanation=explanation,
                    highlighted_attributes=[],
                )
    return result


class WhyThisPersonExplainer:
    """Generates 2-3 sentence explanations with highlighted attributes for search results."""

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name or get_config().llm.search_model

    def prepare_enrichment(self, results: list[SearchResultItem], session: Session) -> dict[str, dict]:
        """Fetch enrichment data for all results upfront. Returns enrichment_map."""
        profile_ids = [r.crawled_profile_id for r in results if r.crawled_profile_id]
        connection_ids = [r.connection_id for r in results if r.connection_id]
        if not profile_ids:
            return {}
        return self._fetch_enrichment_data(session, profile_ids, connection_ids)

    def _create_llm_client(self):
        settings = get_config()
        api_key = settings.openai_api_key or settings.llm_api_key
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name=self._model_name,
            temperature=0,
            api_key=SecretStr(api_key) if api_key else None,
        )
        return LLMFactory.create_client(SystemUser("why-this-person-explainer"), config)

    def _fetch_enrichment_data(
        self,
        session: Session,
        crawled_profile_ids: list[str],
        connection_ids: list[str] | None = None,
    ) -> dict[str, dict]:
        """Fetch full profile context: experiences, education, company metadata, affinity sub-scores.

        Returns: {crawled_profile_id: {experiences, education, skills, affinity, current_company_meta}}
        On any DB failure, returns {} so the caller skips enrichment (Code-2).
        """
        enrichment: dict[str, dict] = {
            pid: {"experiences": [], "education": [], "skills": [], "affinity": {}, "current_company_meta": None}
            for pid in crawled_profile_ids
        }

        try:
            # Experiences with company metadata (no truncation — fetch ALL)
            exp_rows = session.execute(
                text("""
                    SELECT e.crawled_profile_id, e.position, e.company_name,
                           e.start_date, e.end_date, e.is_current,
                           c.industry AS company_industry, c.size_tier AS company_size_tier
                    FROM experience e
                    LEFT JOIN company c ON e.company_id = c.id
                    WHERE e.crawled_profile_id = ANY(:profile_ids)
                    ORDER BY e.start_date DESC NULLS FIRST
                """),
                {"profile_ids": crawled_profile_ids},
            ).fetchall()

            for row in exp_rows:
                pid = str(row.crawled_profile_id)
                if pid in enrichment:
                    enrichment[pid]["experiences"].append({
                        "position": row.position,
                        "company": row.company_name,
                        "start": str(row.start_date) if row.start_date else None,
                        "end": str(row.end_date) if row.end_date else None,
                        "current": row.is_current,
                        "company_industry": row.company_industry,
                        "company_size_tier": row.company_size_tier,
                    })
                    # Set current company metadata
                    if row.is_current and enrichment[pid]["current_company_meta"] is None:
                        enrichment[pid]["current_company_meta"] = {
                            "industry": row.company_industry,
                            "size_tier": row.company_size_tier,
                        }
        except Exception:
            logger.exception("Failed to fetch experiences for explainer")
            return {}

        try:
            # Education
            edu_rows = session.execute(
                text("""
                    SELECT crawled_profile_id, school_name, degree, field_of_study, end_year
                    FROM education
                    WHERE crawled_profile_id = ANY(:profile_ids)
                    ORDER BY end_year DESC NULLS FIRST
                """),
                {"profile_ids": crawled_profile_ids},
            ).fetchall()

            for row in edu_rows:
                pid = str(row.crawled_profile_id)
                if pid in enrichment:
                    enrichment[pid]["education"].append({
                        "school": row.school_name,
                        "degree": row.degree,
                        "field": row.field_of_study,
                        "end_year": row.end_year,
                    })
        except Exception:
            logger.exception("Failed to fetch education for explainer")
            return {}

        try:
            # Skills (all, no truncation)
            skill_rows = session.execute(
                text("""
                    SELECT crawled_profile_id, skill_name
                    FROM profile_skill
                    WHERE crawled_profile_id = ANY(:profile_ids)
                """),
                {"profile_ids": crawled_profile_ids},
            ).fetchall()

            for row in skill_rows:
                pid = str(row.crawled_profile_id)
                if pid in enrichment:
                    enrichment[pid]["skills"].append(row.skill_name)
        except Exception:
            logger.exception("Failed to fetch skills for explainer")
            return {}

        try:
            # Affinity sub-scores from connection table
            if connection_ids:
                affinity_rows = session.execute(
                    text("""
                        SELECT id, affinity_recency, affinity_career_overlap,
                               affinity_mutual_connections, affinity_external_contact,
                               affinity_embedding_similarity
                        FROM connection
                        WHERE id = ANY(:conn_ids)
                    """),
                    {"conn_ids": connection_ids},
                ).fetchall()

                # Build conn_id -> crawled_profile_id mapping from the results
                # We need to map affinity back to crawled_profile_id
                conn_to_profile = {}
                for row in affinity_rows:
                    conn_to_profile[str(row.id)] = row

                # Map back using the items passed to us
                # The caller should pass connection_ids in the same order as crawled_profile_ids
                # but we'll use a separate lookup
                for row in affinity_rows:
                    conn_id = str(row.id)
                    # We need to find the crawled_profile_id for this connection
                    # Look up from the connection table
                    profile_row = session.execute(
                        text("SELECT crawled_profile_id FROM connection WHERE id = :conn_id"),
                        {"conn_id": conn_id},
                    ).fetchone()
                    if profile_row:
                        pid = str(profile_row.crawled_profile_id)
                        if pid in enrichment:
                            enrichment[pid]["affinity"] = {
                                "recency": row.affinity_recency,
                                "career_overlap": row.affinity_career_overlap,
                                "mutual_connections": row.affinity_mutual_connections,
                                "external_contact": row.affinity_external_contact,
                                "embedding_similarity": row.affinity_embedding_similarity,
                            }
        except Exception:
            logger.exception("Failed to fetch affinity sub-scores for explainer")
            # Non-fatal: continue without affinity sub-scores

        return enrichment

    @observe(name="why_this_person_batch")
    def explain_batch(
        self,
        query: str,
        batch: list[SearchResultItem],
        enrichment_map: dict[str, dict],
    ) -> dict[str, ProfileExplanation]:
        """Explain a single batch of profiles. Instrumented as a Langfuse generation."""
        formatted = "\n\n".join(
            _format_profile(r, enrichment_map.get(r.crawled_profile_id))
            for r in batch
        )
        prompt = _PROMPT_TEMPLATE.format(query=query, formatted_profiles=formatted)
        valid_ids = {_profile_key(r) for r in batch}

        try:
            client = self._create_llm_client()
            msg = LLMMessage().add_user_message(prompt)
            raw = client.call_llm(msg)
            return _parse_explanations(raw, valid_ids)
        except Exception:
            logger.exception("WhyThisPersonExplainer batch failed")
            return {}

    @observe(name="why_this_person")
    def explain(
        self,
        query: str,
        results: list[SearchResultItem],
        session: Session | None = None,
    ) -> dict[str, ProfileExplanation]:
        """Return {profile_key: ProfileExplanation} for each result.

        Keys are connection_id when available, otherwise crawled_profile_id.
        Processes in batches of 10 profiles per LLM call.
        """
        if not results:
            return {}

        enrichment_map: dict[str, dict] = {}
        if session:
            enrichment_map = self.prepare_enrichment(results, session)
            if not enrichment_map:
                logger.warning("Skipping explanations: enrichment data fetch failed")
                return {}

        # Process in batches of BATCH_SIZE
        all_explanations: dict[str, ProfileExplanation] = {}
        for i in range(0, len(results), BATCH_SIZE):
            batch = results[i:i + BATCH_SIZE]
            batch_result = self.explain_batch(query, batch, enrichment_map)
            all_explanations.update(batch_result)

        return all_explanations

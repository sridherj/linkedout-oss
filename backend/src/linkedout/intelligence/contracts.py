# SPDX-License-Identifier: Apache-2.0
"""Contracts for the LinkedIn network search agent."""
from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class QueryType(StrEnum):
    SQL = "sql"
    VECTOR = "vector"
    HYBRID = "hybrid"
    DIRECT = "direct"


class SearchRequest(BaseModel):
    """Incoming search request."""
    query: str
    session_id: Optional[str] = None
    limit: int = Field(default=20, le=100)


class SearchResultItem(BaseModel):
    """Shared SSE contract -- Phase 4 produces, Phase 5a consumes."""
    connection_id: str
    crawled_profile_id: str
    full_name: str
    headline: Optional[str] = None
    current_position: Optional[str] = None
    current_company_name: Optional[str] = None
    location_city: Optional[str] = None
    location_country: Optional[str] = None
    linkedin_url: Optional[str] = None
    public_identifier: Optional[str] = None
    affinity_score: Optional[float] = None
    dunbar_tier: Optional[str] = None
    similarity_score: Optional[float] = None
    connected_at: Optional[str] = None
    has_enriched_data: bool = False
    match_context: Optional[dict] = None  # Extra SQL columns explaining why this person matched


class SearchResponse(BaseModel):
    """Full search response returned by SearchAgent.run()."""
    answer: str
    results: list[SearchResultItem]
    query_type: str
    result_count: int
    follow_up_suggestions: list[str] = Field(default_factory=list)


class SearchEvent(BaseModel):
    """SSE event -- Phase 5a consumes via fetch + ReadableStream."""
    type: str  # thinking | result | done | error
    message: Optional[str] = None
    payload: Optional[dict] = None


class HighlightedAttribute(BaseModel):
    """A highlighted attribute chip for a result card."""
    text: str  # e.g. "IC → PM in 18 mo"
    color_tier: int = Field(ge=0, le=2)  # 0=lavender (primary), 1=rose (secondary), 2=sage (tertiary)


class MatchStrength(StrEnum):
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"


class ProfileExplanation(BaseModel):
    """Structured explanation for why a profile matches a query."""
    explanation: str  # 1-2 concise sentences (~40-50 words)
    match_strength: MatchStrength = MatchStrength.PARTIAL
    highlighted_attributes: list[HighlightedAttribute] = Field(default_factory=list, max_length=3)


class IntroPath(BaseModel):
    """A potential introduction path via a mutual connection."""
    via: dict  # {connection_id, name, affinity_score}
    shared_context: str
    strength: str  # strong | moderate | weak


class IntroPathsResponse(BaseModel):
    """Response for warm intro paths endpoint."""
    target: dict  # {connection_id, name}
    intro_paths: list[IntroPath]


# ── Best Hop contracts ─────────────────────────────────────────────────


class BestHopRequest(BaseModel):
    """Incoming best-hop ranking request from the Chrome extension."""
    target_name: str                     # "Chandra Sekhar Kopparthi"
    target_url: str                      # "https://linkedin.com/in/chandrasekharkopparthi"
    mutual_urls: list[str]               # LinkedIn URLs from mutual connections page
    session_id: Optional[str] = None     # Resume existing session (future)


class BestHopResultItem(BaseModel):
    """Single ranked result in best-hop SSE stream.

    The LLM returns rank + why_this_person. Service merges in
    SQL-sourced fields (connection_id, full_name, etc.) before
    emitting as an SSE result event.
    """
    rank: int
    connection_id: str
    crawled_profile_id: str
    full_name: str
    current_position: Optional[str] = None
    current_company_name: Optional[str] = None
    affinity_score: Optional[float] = None
    dunbar_tier: Optional[str] = None
    linkedin_url: Optional[str] = None
    why_this_person: str


class SearchTurnResult(BaseModel):
    """Result of a single conversation turn, including transcript for multi-turn replay."""
    response: SearchResponse
    turn_transcript: list[dict] = Field(default_factory=list)  # Messages from this turn only
    input_token_estimate: int = 0
    output_token_estimate: int = 0


# ── Conversation turn response models (SP6a) ────────────────────────────

class ResultSummaryChip(BaseModel):
    """Inline summary chip in conversation thread."""
    text: str  # e.g. "13 results", "−9 FAANG", "sorted by affinity"
    type: str  # count | filter | sort | removal


class SuggestedAction(BaseModel):
    """Contextual follow-up action hint."""
    type: str  # narrow | rank | exclude | broaden | ask
    label: str  # e.g. "Only Bangalore", "Rank by affinity"


class ResultMetadata(BaseModel):
    """Metadata for results header."""
    count: int = 0
    sort_description: str = ""  # e.g. "sorted by promo recency"


class FacetItem(BaseModel):
    """Single facet value with count."""
    label: str
    count: int


class FacetGroup(BaseModel):
    """Group of facet values for a dimension."""
    group: str  # e.g. "Dunbar Tier", "Location"
    items: list[FacetItem] = Field(default_factory=list)


class ConversationTurnResponse(BaseModel):
    """Structured response for a conversation turn (SP6a.5).

    Every turn response includes the LLM message plus structured metadata
    for the frontend to render conversation thread, result cards, facets,
    excluded-profiles banner, and follow-up hints.
    """
    message: str  # Natural language response text
    result_summary_chips: list[ResultSummaryChip] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    result_metadata: ResultMetadata = Field(default_factory=ResultMetadata)
    facets: list[FacetGroup] = Field(default_factory=list)
    results: list[SearchResultItem] = Field(default_factory=list)
    query_type: str = QueryType.DIRECT
    turn_transcript: list[dict] = Field(default_factory=list)
    input_token_estimate: int = 0
    output_token_estimate: int = 0


# ---------------------------------------------------------------------------
# Profile Detail (SP6b) — slide-over panel data for all 4 tabs
# ---------------------------------------------------------------------------

class KeySignal(BaseModel):
    """A key signal displayed on the Overview tab."""
    icon: str  # emoji or icon name
    label: str  # short uppercase label
    value: str  # full sentence explanation
    color_tier: int = Field(ge=0, le=2)  # 0=purple, 1=rose, 2=sage


class ExperienceItem(BaseModel):
    """A single experience entry for the Experience tab."""
    role: str
    company: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_months: Optional[int] = None
    is_current: bool = False
    company_industry: Optional[str] = None
    company_size_tier: Optional[str] = None


class EducationItem(BaseModel):
    """A single education entry."""
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class SkillItem(BaseModel):
    """A skill with query-relevance flag."""
    name: str
    is_featured: bool = False  # True = relevant to current query


class AffinitySubScore(BaseModel):
    """A sub-score component of the affinity score."""
    name: str
    value: float
    max_value: float = 100.0


class AffinityDetail(BaseModel):
    """Full affinity breakdown for the Affinity tab."""
    score: Optional[float] = None
    tier: Optional[str] = None
    tier_description: Optional[str] = None
    sub_scores: list[AffinitySubScore] = Field(default_factory=list)


class ProfileDetailResponse(BaseModel):
    """Full profile detail for the slide-over panel (all 4 tabs)."""
    # Identity
    connection_id: str
    crawled_profile_id: str
    full_name: str
    headline: Optional[str] = None
    current_position: Optional[str] = None
    current_company_name: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    profile_image_url: Optional[str] = None
    has_enriched_data: bool = False

    # Overview tab
    why_this_person_expanded: Optional[str] = None  # Full paragraph explanation
    key_signals: list[KeySignal] = Field(default_factory=list)

    # Experience tab
    experiences: list[ExperienceItem] = Field(default_factory=list)

    # Education
    education: list[EducationItem] = Field(default_factory=list)

    # Skills
    skills: list[SkillItem] = Field(default_factory=list)

    # Affinity tab
    affinity: Optional[AffinityDetail] = None

    # Connection metadata
    connected_at: Optional[str] = None
    connection_source: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    # Ask tab
    suggested_questions: list[str] = Field(default_factory=list)

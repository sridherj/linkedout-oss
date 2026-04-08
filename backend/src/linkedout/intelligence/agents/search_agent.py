# SPDX-License-Identifier: Apache-2.0
"""SearchAgent -- agentic NL query engine for user-scoped LinkedIn network search."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from shared.utilities.langfuse_guard import observe
from sqlalchemy.orm import Session

from linkedout.intelligence.contracts import (
    ConversationTurnResponse,
    FacetGroup,
    FacetItem,
    QueryType,
    ResultMetadata,
    ResultSummaryChip,
    SearchEvent,
    SearchResponse,
    SearchResultItem,
)
from linkedout.intelligence.schema_context import build_schema_context
from linkedout.intelligence.tools.career_tool import analyze_career_pattern, lookup_role_aliases
from linkedout.intelligence.tools.company_tool import classify_company, resolve_company_aliases
from linkedout.intelligence.tools.intro_tool import find_intro_paths
from linkedout.intelligence.tools.network_tool import get_network_stats
from linkedout.intelligence.tools.profile_tool import get_profile_detail, request_enrichment
from linkedout.intelligence.tools.result_set_tool import (
    compute_facets,
    get_tagged_profiles,
    tag_profiles,
)
from linkedout.intelligence.tools.sql_tool import execute_sql
from linkedout.intelligence.tools.vector_tool import search_profiles
from linkedout.intelligence.tools.web_tool import web_search
from shared.config import get_config
from utilities.llm_manager import LLMFactory, LLMMessage, SystemUser
from utilities.llm_manager.conversation_manager import ConversationManager
from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="backend")

MAX_ITERATIONS = 20

# Fields that map directly to SearchResultItem — everything else goes into match_context.
# Internal fields (app_user_id, etc.) are excluded to prevent leaking into the API payload.
_KNOWN_FIELDS = frozenset({
    "connection_id", "crawled_profile_id", "id",
    "full_name", "headline", "current_position", "current_company_name",
    "location_city", "location_country", "linkedin_url", "public_identifier",
    "affinity_score", "dunbar_tier", "similarity", "connected_at", "has_enriched_data",
})

_EXCLUDE_FIELDS = frozenset({
    "app_user_id", "embedding", "profile_embedding",
})

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "search_system.md"
_SUMMARIZE_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "prompts" / "intelligence" / "summarize_turns.md"

# LangChain tool definitions for bind_tools
_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Execute a SELECT-only SQL query against the user's LinkedIn network database. "
                "The database is automatically scoped to the current user's network — "
                "no user ID filtering is needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_profiles",
            "description": (
                "Semantic vector search over LinkedIn profiles. "
                "Finds people by meaning/concept rather than exact text match."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query describing the kind of people to find.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20, max 100).",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for context not in the database — "
                           "company info, investors, funding details, industry context, "
                           "recent news, executive teams.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_company_aliases",
            "description": (
                "Resolve a company name to its canonical form. Use this BEFORE writing SQL "
                "with company names to get the correct canonical_name for ILIKE patterns. "
                "Returns canonical name, known aliases, subsidiary info, and company metadata."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "Company name to resolve (e.g., 'TCS', 'AWS', 'Google Cloud').",
                    },
                },
                "required": ["company_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_company",
            "description": (
                "Classify companies by type (services/product/startup/enterprise/consulting), "
                "industry, and size. Use when you need to distinguish company types for filtering."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of company names to classify (max 10).",
                    },
                },
                "required": ["company_names"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_career_pattern",
            "description": (
                "Analyze career patterns for specific profiles. Returns tenure, seniority "
                "progression, company type transitions, and career velocity. Use AFTER finding "
                "candidates with SQL to evaluate their career trajectories."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of crawled_profile IDs to analyze (max 20).",
                    },
                },
                "required": ["profile_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_role_aliases",
            "description": (
                "Look up canonical role titles and their aliases. Use to find all title "
                "variants for a role concept (e.g., 'senior engineer' -> 'Sr. SDE', "
                "'Senior Software Engineer', etc.) before writing SQL with position filters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "role_query": {
                        "type": "string",
                        "description": "Role title or keyword to search for.",
                    },
                },
                "required": ["role_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_intro_paths",
            "description": (
                "Find introduction paths to a target company or person. Returns tiered paths: "
                "Tier 1 (direct connections at target), Tier 2 (alumni who previously worked there), "
                "Tier 3 (headline mentions — people referencing target in their headline), "
                "Tier 4 (shared-company warm paths — connections who worked at same prior companies as target employees), "
                "Tier 5 (investor connections — connections at firms that invested in target). "
                "Use for 'who can intro me to X' or 'who do I know at Y' queries."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target company name or person name.",
                    },
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_network_stats",
            "description": (
                "Get summary statistics about the user's network: total connections, top companies, "
                "top industries, seniority distribution, top locations. Use to calibrate your "
                "understanding of the network before writing complex queries."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_profile_detail",
            "description": (
                "Get comprehensive profile detail for a specific connection. Returns full data for "
                "all profile tabs: identity, complete experience timeline, education, skills, "
                "affinity breakdown with sub-scores, connection metadata, and tags. "
                "Use when the user asks about a specific person, clicks a profile, or asks "
                "questions like 'tell me more about X' or 'how long has X been in Y'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "The connection ID to look up (e.g., 'conn_abc123').",
                    },
                },
                "required": ["connection_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_enrichment",
            "description": (
                "Request external enrichment for a profile that has only basic data. "
                "This tool checks the profile state and returns a confirmation message. "
                "You MUST relay this confirmation to the user and wait for their approval "
                "before any external API calls are made. NEVER auto-trigger enrichment."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "connection_id": {
                        "type": "string",
                        "description": "The connection ID to enrich.",
                    },
                },
                "required": ["connection_id"],
            },
        },
    },
    # ── Ordering tool ─────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "set_result_order",
            "description": (
                "Set the final display order of search results. Call this AFTER you've gathered "
                "and evaluated candidates, BEFORE writing your final summary. Pass the `id` or "
                "`crawled_profile_id` values from tool results in the order you want them "
                "displayed (most relevant first). Any gathered profiles not in this list will "
                "appear after the ordered ones."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of crawled_profile_id values, best match first.",
                    },
                },
                "required": ["profile_ids"],
            },
        },
    },
    # ── Persistent tools — tag/facet operations ────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "tag_profiles",
            "description": (
                "Add or remove a tag on specific profiles. Tags persist across sessions. "
                "Use for 'tag Priya as shortlist-ml' or 'save these as finalists'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "profile_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "crawled_profile IDs to tag.",
                    },
                    "tag_name": {
                        "type": "string",
                        "description": "Tag label (e.g., 'shortlist-ml', 'finalists').",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["add", "remove"],
                        "description": "Whether to add or remove the tag.",
                        "default": "add",
                    },
                },
                "required": ["profile_ids", "tag_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tagged_profiles",
            "description": (
                "Retrieve profiles with a specific tag. Use for 'show my shortlist' or "
                "'who did I tag as finalists?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tag_name": {
                        "type": "string",
                        "description": "Tag to look up.",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional: scope to a specific session. Omit for all sessions.",
                    },
                },
                "required": ["tag_name"],
            },
        },
    },
]


def _load_system_prompt(schema_context: str, network_preferences: str | None, result_limit: int = 20) -> str:
    """Load and render the system prompt template."""
    preferences_text = (
        network_preferences.strip()
        if network_preferences and network_preferences.strip()
        else "No specific preferences set."
    )
    template = _PROMPT_PATH.read_text()
    return (
        template
        .replace("{schema_context}", schema_context)
        .replace("{network_preferences}", preferences_text)
        .replace("{result_limit}", str(result_limit))
    )


def _load_summarization_prompt() -> str:
    """Load the summarization prompt for ConversationManager."""
    return _SUMMARIZE_PROMPT_PATH.read_text()


def _rows_to_result_items(rows: list[dict]) -> list[SearchResultItem]:
    """Convert raw DB rows (from vector_tool) to SearchResultItem list."""
    items = []
    for row in rows:
        items.append(SearchResultItem(
            connection_id=str(row.get("connection_id", "")),
            crawled_profile_id=str(row.get("id", "")),
            full_name=row.get("full_name") or "",
            headline=row.get("headline"),
            current_position=row.get("current_position"),
            current_company_name=row.get("current_company_name"),
            location_city=row.get("location_city"),
            location_country=row.get("location_country"),
            linkedin_url=row.get("linkedin_url"),
            public_identifier=row.get("public_identifier"),
            affinity_score=row.get("affinity_score"),
            dunbar_tier=row.get("dunbar_tier"),
            similarity_score=row.get("similarity"),
            connected_at=str(row["connected_at"]) if row.get("connected_at") else None,
            has_enriched_data=bool(row.get("has_enriched_data", False)),
        ))
    return items


def _sql_rows_to_result_items(columns: list[str], rows: list[list]) -> list[SearchResultItem]:
    """Convert raw SQL result rows to SearchResultItem list, best-effort mapping."""
    items = []
    col_map = {c: i for i, c in enumerate(columns)}

    for row in rows:
        def _get(name: str, default=None):
            idx = col_map.get(name)
            return row[idx] if idx is not None else default

        connection_id = str(_get("connection_id") or "")
        crawled_profile_id = str(_get("crawled_profile_id") or _get("id") or "")
        if not connection_id and not crawled_profile_id:
            continue

        # Collect extra columns into match_context
        extra = {}
        for col_name, col_idx in col_map.items():
            if col_name not in _KNOWN_FIELDS and col_name not in _EXCLUDE_FIELDS:
                val = row[col_idx]
                if val is not None:
                    extra[col_name] = val

        item = SearchResultItem(
            connection_id=connection_id,
            crawled_profile_id=crawled_profile_id,
            full_name=_get("full_name") or "",
            headline=_get("headline"),
            current_position=_get("current_position"),
            current_company_name=_get("current_company_name"),
            location_city=_get("location_city"),
            location_country=_get("location_country"),
            linkedin_url=_get("linkedin_url"),
            public_identifier=_get("public_identifier"),
            affinity_score=_get("affinity_score"),
            dunbar_tier=_get("dunbar_tier"),
            similarity_score=_get("similarity"),
            connected_at=str(_get("connected_at")) if _get("connected_at") else None,
            has_enriched_data=bool(_get("has_enriched_data", False)),
            match_context=extra if extra else None,
        )
        items.append(item)
    return items


class SearchAgent:
    """Agentic NL query engine for user-scoped LinkedIn network search.

    Uses LLM tool-calling to route queries to SQL or vector search,
    iterating until the LLM produces a final text answer.
    """

    def __init__(
        self,
        session: Session,
        app_user_id: str,
        session_id: str | None = None,
        tenant_id: str | None = None,
        bu_id: str | None = None,
    ):
        self._session = session
        self._app_user_id = app_user_id
        self._session_id = session_id
        self._tenant_id = tenant_id
        self._bu_id = bu_id
        self._schema_context = build_schema_context(session)
        self._model_name = get_config().llm.search_model
        from organization.entities.app_user_entity import AppUserEntity
        app_user = session.get(AppUserEntity, app_user_id)
        raw_prefs = app_user.network_preferences if app_user else None
        self._network_preferences = raw_prefs if isinstance(raw_prefs, str) else None
        self._web_search_count: dict = {"count": 0}
        self._declared_order: list[str] = []
        self._last_candidate_count: int = 0

    def _create_llm_client(self):
        settings = get_config()
        api_key = settings.openai_api_key or settings.llm_api_key
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name=self._model_name,
            api_key=api_key,
            temperature=0,
        )
        return LLMFactory.create_client(SystemUser("search-agent"), config)

    def _build_system_prompt(self, result_limit: int = 20) -> str:
        return _load_system_prompt(self._schema_context, self._network_preferences, result_limit)

    def _create_conversation_manager(self) -> ConversationManager:
        """Create a ConversationManager for building turn history."""
        client = self._create_llm_client()
        prompt = _load_summarization_prompt()
        return ConversationManager(llm_client=client, summarization_prompt=prompt)

    @observe(name="tool_call")
    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a tool call and return serialised result."""
        if tool_name == "execute_sql":
            result = execute_sql(
                query=tool_args["query"],
                session=self._session,
            )
            self._last_candidate_count = len(result.get("rows", [])) if isinstance(result, dict) else 0
            return json.dumps(result, default=str)
        elif tool_name == "search_profiles":
            rows = search_profiles(
                query=tool_args["query"],
                session=self._session,
                limit=tool_args.get("limit", 20),
            )
            self._last_candidate_count = len(rows)
            return json.dumps(rows, default=str)
        elif tool_name == "web_search":
            return web_search(tool_args["query"], _call_count=self._web_search_count)
        elif tool_name == "resolve_company_aliases":
            result = resolve_company_aliases(
                company_name=tool_args["company_name"],
                session=self._session,
            )
            return json.dumps(result, default=str)
        elif tool_name == "classify_company":
            result = classify_company(
                company_names=tool_args["company_names"],
                session=self._session,
            )
            return json.dumps(result, default=str)
        elif tool_name == "analyze_career_pattern":
            result = analyze_career_pattern(
                profile_ids=tool_args["profile_ids"],
                session=self._session,
            )
            return json.dumps(result, default=str)
        elif tool_name == "lookup_role_aliases":
            result = lookup_role_aliases(
                role_query=tool_args["role_query"],
                session=self._session,
            )
            return json.dumps(result, default=str)
        elif tool_name == "find_intro_paths":
            result = find_intro_paths(
                target=tool_args["target"],
                session=self._session,
            )
            self._last_candidate_count = len(result.get("paths", [])) if isinstance(result, dict) else 0
            return json.dumps(result, default=str)
        elif tool_name == "get_network_stats":
            result = get_network_stats(
                session=self._session,
            )
            return json.dumps(result, default=str)
        elif tool_name == "get_profile_detail":
            result = get_profile_detail(
                connection_id=tool_args["connection_id"],
                session=self._session,
                query=tool_args.get("query"),
            )
            return json.dumps(result, default=str)
        elif tool_name == "request_enrichment":
            result = request_enrichment(
                connection_id=tool_args["connection_id"],
                session=self._session,
            )
            return json.dumps(result, default=str)
        elif tool_name == "tag_profiles":
            result = tag_profiles(
                session=self._session,
                app_user_id=self._app_user_id,
                session_id=self._session_id or "",
                tenant_id=self._tenant_id or "",
                bu_id=self._bu_id or "",
                profile_ids=tool_args["profile_ids"],
                tag_name=tool_args["tag_name"],
                action=tool_args.get("action", "add"),
            )
            return json.dumps(result, default=str)
        elif tool_name == "get_tagged_profiles":
            result = get_tagged_profiles(
                session=self._session,
                app_user_id=self._app_user_id,
                tag_name=tool_args["tag_name"],
                session_id=tool_args.get("session_id"),
            )
            return json.dumps(result, default=str)
        elif tool_name == "set_result_order":
            self._declared_order = tool_args.get("profile_ids", [])
            self._last_candidate_count = 0
            return json.dumps({
                "status": "ok",
                "ordered_count": len(self._declared_order),
            })
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})

    def _execute_tool_with_retry(self, tool_name: str, tool_args: dict) -> str:
        """Execute tool, returning error+hint on SQL failures so the LLM can self-correct."""
        result_str = self._execute_tool(tool_name, tool_args)
        return result_str

    def _determine_query_type(self, messages: list[dict]) -> str:
        """Determine query type from tool calls made during the conversation."""
        tools_used: set[str] = set()
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tools_used.add(tc["name"])

        sql_tools = {"execute_sql", "find_intro_paths", "resolve_company_aliases",
                     "classify_company", "analyze_career_pattern", "lookup_role_aliases",
                     "get_network_stats"}
        used_sql = bool(tools_used & sql_tools)
        used_vector = "search_profiles" in tools_used

        if used_sql and used_vector:
            return QueryType.HYBRID
        if used_sql:
            return QueryType.SQL
        if used_vector:
            return QueryType.VECTOR
        return QueryType.DIRECT

    def _collect_results(self, messages: list[dict]) -> list[SearchResultItem]:
        """Collect SearchResultItems from all tool responses."""
        items: list[SearchResultItem] = []
        tool_call_names: dict[str, str] = {}
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tool_call_names[tc["id"]] = tc["name"]
            if msg.get("role") == "tool":
                try:
                    data = json.loads(msg["content"])
                except (json.JSONDecodeError, TypeError):
                    continue

                tool_name = tool_call_names.get(msg.get("tool_call_id", ""), "")

                if tool_name == "search_profiles" and isinstance(data, list):
                    items.extend(_rows_to_result_items(data))
                elif tool_name == "execute_sql" and isinstance(data, dict) and data.get("columns"):
                    items.extend(_sql_rows_to_result_items(data["columns"], data.get("rows", [])))
                elif tool_name == "find_intro_paths" and isinstance(data, dict) and data.get("paths"):
                    for p in data["paths"]:
                        items.append(SearchResultItem(
                            connection_id="",
                            crawled_profile_id=str(p.get("profile_id", "")),
                            full_name=p.get("intermediary", ""),
                            current_position=p.get("current_role"),
                            current_company_name=p.get("company") or p.get("current_company"),
                            affinity_score=p.get("affinity_score"),
                            dunbar_tier=p.get("dunbar_tier"),
                            match_context={"tier": p.get("tier"), "path_type": p.get("path_type")},
                        ))
                elif tool_name == "analyze_career_pattern" and isinstance(data, dict) and data.get("profiles"):
                    for p in data["profiles"]:
                        items.append(SearchResultItem(
                            connection_id="",
                            crawled_profile_id=str(p.get("id", "")),
                            full_name=p.get("name", ""),
                            match_context={"career_velocity": p.get("career_velocity"), "avg_tenure_years": p.get("avg_tenure_years")},
                        ))

        # Merge dedup: combine match_context, fill nulls from later occurrences
        merged: dict[str, SearchResultItem] = {}
        for item in items:
            key = item.crawled_profile_id or item.connection_id
            if not key:
                continue
            if key not in merged:
                merged[key] = item
            else:
                existing = merged[key]
                # Merge match_context dicts
                if item.match_context:
                    existing.match_context = {**(existing.match_context or {}), **item.match_context}
                # Fill null fields from later occurrence
                for field in ('full_name', 'headline', 'current_position', 'current_company_name',
                              'location_city', 'location_country', 'linkedin_url', 'public_identifier',
                              'affinity_score', 'dunbar_tier', 'connected_at', 'has_enriched_data', 'similarity_score'):
                    if getattr(existing, field) is None and getattr(item, field) is not None:
                        setattr(existing, field, getattr(item, field))

        # Apply declared ordering if set
        if self._declared_order:
            order_map = {pid: i for i, pid in enumerate(self._declared_order)}
            ordered = []
            unordered = []
            for key, item in merged.items():
                if key in order_map:
                    ordered.append((order_map[key], item))
                else:
                    unordered.append(item)
            ordered.sort(key=lambda x: x[0])
            return [item for _, item in ordered] + unordered
        else:
            return list(merged.values())

    @observe(name="search_agent_run")
    def run(
        self,
        query: str,
        turn_history: list[dict[str, Any]] | None = None,
        limit: int = 20,
    ) -> SearchResponse:
        """Synchronous search -- returns full result set.

        Args:
            query: The user's search query.
            turn_history: Prior turn dicts from DB (keys: user_query, transcript, summary).
            limit: Max results.
        """
        self._web_search_count = {"count": 0}
        self._declared_order = []
        self._last_candidate_count = 0
        client = self._create_llm_client()

        system_prompt = self._build_system_prompt(result_limit=limit)
        msg = LLMMessage()
        msg.add_system_message(system_prompt)

        # Inject conversation history via ConversationManager
        if turn_history:
            conv_manager = self._create_conversation_manager()
            summary_result = conv_manager.build_history(turn_history)
            for hist_msg in summary_result.messages:
                role = hist_msg.get("role", "")
                content = hist_msg.get("content", "")
                if role == "user":
                    msg.add_user_message(content)
                elif role == "assistant":
                    msg.add_assistant_message(content)

        msg.add_user_message(query)

        # Tool-calling loop
        for iteration in range(MAX_ITERATIONS):
            response = client.call_llm_with_tools(msg, _TOOL_DEFINITIONS)
            msg.add_assistant_message(response.content, tool_calls=response.tool_calls if response.has_tool_calls else None)

            if not response.has_tool_calls:
                break

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                logger.info(f"Iteration {iteration + 1}: calling {tool_name} with {tool_args}")

                result_str = self._execute_tool_with_retry(tool_name, tool_args)
                msg.add_tool_message(result_str, tool_call_id=tool_call["id"])
        else:
            logger.warning(f"SearchAgent hit MAX_ITERATIONS ({MAX_ITERATIONS}) without final answer")

        # Extract final answer
        all_messages = msg.get_messages()
        final_text = ""
        if all_messages and all_messages[-1].get("role") == "assistant":
            final_text = str(all_messages[-1].get("content", ""))
        elif all_messages and all_messages[-1].get("role") == "tool":
            final_text = "Search completed. See results below."

        results = self._collect_results(all_messages)
        query_type = self._determine_query_type(all_messages)

        return SearchResponse(
            answer=final_text,
            results=results,
            query_type=query_type,
            result_count=len(results),
            follow_up_suggestions=[],
        )

    @observe(name="search_agent_run_turn")
    def run_turn(
        self,
        query: str,
        turn_history: list[dict[str, Any]] | None = None,
        limit: int = 20,
    ) -> ConversationTurnResponse:
        """Run a single conversation turn with full transcript capture.

        Args:
            query: The user's search query.
            turn_history: Prior turn dicts from DB (keys: user_query, transcript, summary).
            limit: Max results.
        """
        client = self._create_llm_client()
        self._web_search_count = {"count": 0}
        self._declared_order = []
        self._last_candidate_count = 0

        system_prompt = self._build_system_prompt(result_limit=limit)
        msg = LLMMessage()
        msg.add_system_message(system_prompt)

        # Inject conversation history via ConversationManager
        if turn_history:
            conv_manager = self._create_conversation_manager()
            summary_result = conv_manager.build_history(turn_history)
            for hist_msg in summary_result.messages:
                role = hist_msg.get("role", "")
                content = hist_msg.get("content", "")
                if role == "user":
                    msg.add_user_message(content)
                elif role == "assistant":
                    msg.add_assistant_message(content)

        # Track where the current turn starts (after system + history)
        turn_start_idx = len(msg.get_messages())

        msg.add_user_message(query)

        # Tool-calling loop
        import time as _time
        turn_t0 = _time.perf_counter()
        tools_used_this_turn: list[str] = []
        current_result_set: list[dict] = []
        for iteration in range(MAX_ITERATIONS):
            llm_t0 = _time.perf_counter()
            response = client.call_llm_with_tools(msg, _TOOL_DEFINITIONS)
            llm_ms = round((_time.perf_counter() - llm_t0) * 1000)
            msg.add_assistant_message(response.content, tool_calls=response.tool_calls if response.has_tool_calls else None)

            if not response.has_tool_calls:
                logger.info(f"Turn iteration {iteration + 1}: LLM final answer in {llm_ms}ms")
                break

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tools_used_this_turn.append(tool_name)
                logger.info(f"Turn iteration {iteration + 1}: LLM decided in {llm_ms}ms, calling {tool_name}")
                tool_t0 = _time.perf_counter()
                result_str = self._execute_tool_with_retry(tool_name, tool_args)
                tool_ms = round((_time.perf_counter() - tool_t0) * 1000)
                logger.info(f"Turn iteration {iteration + 1}: {tool_name} executed in {tool_ms}ms")
                msg.add_tool_message(result_str, tool_call_id=tool_call["id"])

                # Track result set from search tools
                if tool_name in ("execute_sql", "search_profiles"):
                    try:
                        data = json.loads(result_str)
                        if tool_name == "search_profiles" and isinstance(data, list):
                            current_result_set = data
                        elif tool_name == "execute_sql" and isinstance(data, dict) and data.get("columns"):
                            cols = data["columns"]
                            rows = data.get("rows", [])
                            current_result_set = [
                                dict(zip(cols, row)) for row in rows
                            ]
                    except (json.JSONDecodeError, TypeError):
                        pass
        else:
            logger.warning(f"SearchAgent hit MAX_ITERATIONS ({MAX_ITERATIONS}) without final answer")

        total_turn_ms = round((_time.perf_counter() - turn_t0) * 1000)
        logger.info(f"Turn complete: {len(tools_used_this_turn)} tool calls, {total_turn_ms}ms total, tools: {tools_used_this_turn}")

        all_messages = msg.get_messages()

        # Extract final answer
        final_text = ""
        if all_messages and all_messages[-1].get("role") == "assistant":
            final_text = str(all_messages[-1].get("content", ""))
        elif all_messages and all_messages[-1].get("role") == "tool":
            final_text = "Search completed. See results below."

        results = self._collect_results(all_messages)
        query_type = self._determine_query_type(all_messages)

        # Extract this turn's messages
        turn_transcript = all_messages[turn_start_idx:]

        # Estimate tokens (rough: 1 token ~ 4 chars)
        input_chars = sum(len(str(m.get("content", ""))) for m in all_messages[:turn_start_idx + 1])
        output_chars = sum(len(str(m.get("content", ""))) for m in turn_transcript[1:])

        # Compute facets from current result set
        facets_raw = compute_facets(current_result_set)
        facet_groups = [
            FacetGroup(
                group=fg["group"],
                items=[FacetItem(label=fi["label"], count=fi["count"]) for fi in fg["items"]],
            )
            for fg in facets_raw
        ]

        # Build result summary chips
        chips = []
        if len(results) > 0:
            chips.append(ResultSummaryChip(text=f"{len(results)} results", type="count"))

        return ConversationTurnResponse(
            message=final_text,
            results=results,
            query_type=query_type,
            result_metadata=ResultMetadata(
                count=len(results),
                sort_description="",
            ),
            facets=facet_groups,
            result_summary_chips=chips,
            suggested_actions=[],
            turn_transcript=turn_transcript,
            input_token_estimate=input_chars // 4,
            output_token_estimate=output_chars // 4,
        )

    async def run_streaming(
        self, query: str, turn_history: list[dict[str, Any]] | None = None, limit: int = 20
    ) -> AsyncGenerator[SearchEvent, None]:
        """Async streaming -- yields SSE events."""
        queue: asyncio.Queue[SearchEvent | None] = asyncio.Queue()

        def _sync_run():
            """Run the sync tool-calling loop, pushing events to queue."""
            try:
                self._web_search_count = {"count": 0}
                self._declared_order = []
                self._last_candidate_count = 0
                queue.put_nowait(SearchEvent(type="thinking", message="Routing query..."))

                client = self._create_llm_client()
                system_prompt = self._build_system_prompt(result_limit=limit)
                msg = LLMMessage()
                msg.add_system_message(system_prompt)

                # Inject conversation history via ConversationManager
                if turn_history:
                    conv_manager = self._create_conversation_manager()
                    summary_result = conv_manager.build_history(turn_history)
                    for hist_msg in summary_result.messages:
                        role = hist_msg.get("role", "")
                        content = hist_msg.get("content", "")
                        if role == "user":
                            msg.add_user_message(content)
                        elif role == "assistant":
                            msg.add_assistant_message(content)

                msg.add_user_message(query)

                for iteration in range(MAX_ITERATIONS):
                    response = client.call_llm_with_tools(msg, _TOOL_DEFINITIONS)
                    msg.add_assistant_message(response.content, tool_calls=response.tool_calls if response.has_tool_calls else None)

                    if not response.has_tool_calls:
                        break

                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]
                        queue.put_nowait(SearchEvent(
                            type="thinking",
                            message=f"Querying database ({tool_name})...",
                        ))

                        result_str = self._execute_tool_with_retry(tool_name, tool_args)
                        msg.add_tool_message(result_str, tool_call_id=tool_call["id"])

                        # Emit progress using C4 candidate count (set by _execute_tool)
                        if self._last_candidate_count > 0:
                            queue.put_nowait(SearchEvent(
                                type="thinking",
                                message=f"Found {self._last_candidate_count} candidates, evaluating...",
                            ))

                # Collect ordered results after the agent loop
                all_messages = msg.get_messages()
                results = self._collect_results(all_messages)

                # Emit a single batch results event
                queue.put_nowait(SearchEvent(
                    type="results",
                    payload={
                        "items": [item.model_dump(mode="json") for item in results],
                    },
                ))

                # Final answer
                final_text = ""
                if all_messages and all_messages[-1].get("role") == "assistant":
                    final_text = str(all_messages[-1].get("content", ""))

                query_type = self._determine_query_type(all_messages)
                queue.put_nowait(SearchEvent(
                    type="done",
                    payload={
                        "total": len(results),
                        "query_type": query_type,
                        "answer": final_text,
                    },
                ))
            except Exception as e:
                logger.exception("SearchAgent streaming error")
                queue.put_nowait(SearchEvent(type="error", message=str(e)))
            finally:
                queue.put_nowait(None)  # sentinel

        # Run sync loop in a thread
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, _sync_run)

        # Yield events from queue
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

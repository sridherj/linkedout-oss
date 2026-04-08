# SPDX-License-Identifier: Apache-2.0
"""Live LLM test for best-hop ranking — hits real LLM API.

Uses real profile data (Manjusha Tadepalli as target, real mutual connections
with actual crawled_profile_id UUIDs) to validate that the LLM returns
parseable JSON with correct IDs — not fabricated short IDs.

Run with: pytest -m live_llm tests/live_llm/ -k best_hop -v
"""
from __future__ import annotations

import pytest

from linkedout.intelligence.services.best_hop_service import (
    BestHopContext,
    BestHopService,
)

pytestmark = pytest.mark.live_llm


def _make_manjusha_context() -> tuple[BestHopContext, set[str]]:
    """Build context from real Manjusha Tadepalli data and her mutual connections.

    Returns (context, valid_ids) where valid_ids is the set of real crawled_profile_ids.
    """
    target_profile = {
        "id": "cp_NW0DkPyIpcn_69BK4jRZz",
        "full_name": "Manjusha Tadepalli",
        "headline": "Human Resources Consultant at ValueMomentum",
        "current_position": "Human Resources Consultant",
        "current_company_name": "ValueMomentum",
        "location_city": "Hyderabad",
        "seniority_level": None,
        "about": "I choose the best and make the right choice for you. Don't step back to Seek my help. I'm always ready to help.",
    }
    target_experience: list[dict] = []  # No experience records in DB for this profile

    mutuals = [
        {
            "id": "cp_2JN4x8ONLpkL5f-jwdudX",
            "full_name": "Sagar Raina",
            "headline": "Talent Acquisition Leader ex Airtel, Makemytrip, Delhivery",
            "current_position": "Talent Acquisition Leader ex Airtel, Makemytrip, Delhivery",
            "current_company_name": "PeopleSquare Human Resources Consulting",
            "linkedin_url": "https://www.linkedin.com/in/sagar-raina-9933ba2",
            "location_city": "Gurgaon",
            "seniority_level": None,
            "about": "21 years of experience in Talent Acquisition with more than 10 years in TA Leadership roles.",
            "connection_id": "conn_LUhuMvVxVjl_gHqlD3EaJ",
            "affinity_score": 31.0,
            "dunbar_tier": "acquaintance",
            "affinity_career_overlap": 0.0,
            "affinity_external_contact": 0.7,
            "affinity_recency": 0.2,
            "connected_at": "2015-08-24",
        },
        {
            "id": "cp_085YicrCbxCl51uIS0xLZ",
            "full_name": "Deepti Gupta",
            "headline": "AVP Business Strategy at Pylon Management Consulting",
            "current_position": "AVP Business Strategy at Pylon Management Consulting",
            "current_company_name": "Pylon Management Consulting",
            "linkedin_url": "https://www.linkedin.com/in/deepti-gupta-4009a3137",
            "location_city": "Bengaluru",
            "seniority_level": "vp",
            "about": "Dynamic and results-driven business strategist with over 5 years of experience.",
            "connection_id": "conn_1TGUQK5C6g5hmqv2hTL_6",
            "affinity_score": 18.3,
            "dunbar_tier": "acquaintance",
            "affinity_career_overlap": 0.0,
            "affinity_external_contact": 0.0,
            "affinity_recency": 1.0,
            "connected_at": "2025-06-22",
        },
        {
            "id": "cp_kUhapHEZkBqagnkoj_T5_",
            "full_name": "Kajal Yadav",
            "headline": "Data Scientist@Fractal | AI | ML | DL | GenAI | Tech-Blogger",
            "current_position": "Data Scientist@Fractal",
            "current_company_name": "Fractal",
            "linkedin_url": "https://www.linkedin.com/in/techykajal",
            "location_city": "Delhi",
            "seniority_level": "mid",
            "about": "I'm a Data Scientist by profession, an AI enthusiast by passion.",
            "connection_id": "conn_Z7rFDpB1zGe6Stl7kyPEi",
            "affinity_score": 12.9,
            "dunbar_tier": "acquaintance",
            "affinity_career_overlap": 0.0,
            "affinity_external_contact": 0.0,
            "affinity_recency": 0.2,
            "connected_at": "2020-07-21",
        },
        {
            "id": "cp_OEGqJNecXijFy9rZh_kMx",
            "full_name": "Gaurav Prakash",
            "headline": "Deloitte USI | Advanced Analytics & AI/GenAI | Retail Analytics",
            "current_position": "Deloitte USI | Advanced Analytics & AI/GenAI",
            "current_company_name": "Deloitte",
            "linkedin_url": "https://www.linkedin.com/in/gauravpks",
            "location_city": "Gurgaon",
            "seniority_level": "manager",
            "about": "Engineering and Management Post Graduate with more than twelve years of work experience.",
            "connection_id": "conn_DLGv-KbXpd4iBCIOJYHu6",
            "affinity_score": 11.5,
            "dunbar_tier": "acquaintance",
            "affinity_career_overlap": 0.0,
            "affinity_external_contact": 0.0,
            "affinity_recency": 0.2,
            "connected_at": "2021-02-02",
        },
        {
            "id": "cp_M4PLI82ByR2s5aenQo1_L",
            "full_name": "Anubhav Bhargava",
            "headline": "Building Eywa",
            "current_position": "Building Eywa",
            "current_company_name": "Eywa",
            "linkedin_url": "https://www.linkedin.com/in/anbhvb",
            "location_city": "Bengaluru",
            "seniority_level": "founder",
            "about": None,
            "connection_id": "conn_GRMiVHxilIBfJe3jxL8Ub",
            "affinity_score": 11.4,
            "dunbar_tier": "acquaintance",
            "affinity_career_overlap": 0.0,
            "affinity_external_contact": 0.0,
            "affinity_recency": 0.2,
            "connected_at": "2019-06-22",
        },
    ]

    mutual_experience = {
        "cp_2JN4x8ONLpkL5f-jwdudX": [
            {"company_name": "PeopleSquare Human Resources Consulting", "position": "Managing Partner -Technology Hiring",
             "start_date": "2023-06-01", "end_date": None, "is_current": True, "seniority_level": None},
            {"company_name": "airtel", "position": "SVP-Head Talent Acquisition",
             "start_date": None, "end_date": None, "is_current": None, "seniority_level": "vp"},
            {"company_name": "Delhivery", "position": "SVP-Head Talent Acquisition",
             "start_date": None, "end_date": None, "is_current": None, "seniority_level": "vp"},
            {"company_name": "MakeMyTrip.com", "position": "Director-Talent Acquisition",
             "start_date": None, "end_date": None, "is_current": None, "seniority_level": "director"},
        ],
        "cp_085YicrCbxCl51uIS0xLZ": [
            {"company_name": "Pylon Management Consulting", "position": "AVP Business Strategy",
             "start_date": "2024-04-01", "end_date": None, "is_current": True, "seniority_level": "vp"},
            {"company_name": "Kelly Services India", "position": "Executive",
             "start_date": "2019-12-01", "end_date": "2021-01-01", "is_current": None, "seniority_level": None},
        ],
        "cp_kUhapHEZkBqagnkoj_T5_": [
            {"company_name": "Fractal", "position": "Data Scientist",
             "start_date": "2024-02-01", "end_date": None, "is_current": True, "seniority_level": "mid"},
            {"company_name": "Hexo", "position": "Machine Learning Engineer",
             "start_date": "2023-02-01", "end_date": "2023-10-01", "is_current": None, "seniority_level": "mid"},
        ],
        "cp_OEGqJNecXijFy9rZh_kMx": [
            {"company_name": "Deloitte", "position": "Manager",
             "start_date": "2022-05-01", "end_date": None, "is_current": True, "seniority_level": "manager"},
            {"company_name": "HCL Technologies", "position": "Associate Manager",
             "start_date": "2017-07-01", "end_date": "2021-03-01", "is_current": None, "seniority_level": "manager"},
        ],
        "cp_M4PLI82ByR2s5aenQo1_L": [
            {"company_name": "Eywa", "position": "Co-Founder",
             "start_date": "2024-04-01", "end_date": None, "is_current": True, "seniority_level": "founder"},
            {"company_name": "Jumbotail", "position": "Software Engineer",
             "start_date": "2019-07-01", "end_date": "2022-09-01", "is_current": None, "seniority_level": "mid"},
        ],
    }

    valid_ids = {m["id"] for m in mutuals}

    context = BestHopContext(
        target_profile=target_profile,
        target_experience=target_experience,
        target_connection=None,
        mutuals=mutuals,
        mutual_experience=mutual_experience,
        matched_count=5,
        unmatched_count=1,
        unmatched_urls=["https://www.linkedin.com/in/jatin-sharma-csm"],
    )

    return context, valid_ids


class TestBestHopRankingLive:
    """Real LLM call with pre-assembled context — validates output format and ID fidelity."""

    def test_llm_returns_valid_ranked_json_with_real_ids(self):
        """LLM produces parseable JSON array referencing actual crawled_profile_id UUIDs."""
        context, valid_ids = _make_manjusha_context()

        # Build prompt using the real service
        service = BestHopService.__new__(BestHopService)
        prompt = service.build_prompt(context)

        # Verify prompt includes real IDs (the fix we're testing)
        for pid in valid_ids:
            assert pid in prompt, f"crawled_profile_id {pid} missing from prompt"

        # Verify prompt includes key context
        assert "Manjusha Tadepalli" in prompt
        assert "ValueMomentum" in prompt
        assert "Sagar Raina" in prompt

        # Make a real LLM call
        from shared.config.config import backend_config
        from utilities.llm_manager import LLMFactory, LLMMessage, SystemUser
        from utilities.llm_manager.llm_schemas import LLMConfig, LLMProvider

        model_name = getattr(backend_config, "llm", None) and backend_config.llm.search_model or "gpt-4o-mini"
        api_key = backend_config.openai_api_key
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name=model_name,
            api_key=api_key,
            temperature=0,
        )
        client = LLMFactory.create_client(SystemUser("best-hop-live-test"), config)

        msg = LLMMessage()
        msg.add_system_message(prompt)
        msg.add_user_message(
            "Rank the top mutual connections for introducing me to Manjusha Tadepalli. "
            "Return a JSON array with objects containing: crawled_profile_id, rank, why_this_person."
        )

        response = client.call_llm_with_tools(msg, [])

        # Parse with the real parser
        ranked_items = service._parse_llm_response(response.content)

        # Validate structure
        assert isinstance(ranked_items, list), f"Expected list, got {type(ranked_items)}"
        assert len(ranked_items) >= 1, "LLM returned no rankings"
        assert len(ranked_items) <= 5, f"Expected at most 5 rankings, got {len(ranked_items)}"

        for item in ranked_items:
            assert "crawled_profile_id" in item, f"Missing crawled_profile_id: {item}"
            assert "rank" in item, f"Missing rank: {item}"
            assert "why_this_person" in item, f"Missing why_this_person: {item}"

            # This is the critical assertion — IDs must be real UUIDs, not fabricated
            assert item["crawled_profile_id"] in valid_ids, (
                f"LLM returned unknown/fabricated profile ID: {item['crawled_profile_id']}. "
                f"Valid IDs: {valid_ids}"
            )
            assert isinstance(item["rank"], int), f"rank should be int: {item['rank']}"
            assert len(item["why_this_person"]) > 10, (
                f"why_this_person too short: {item['why_this_person']}"
            )

        # Ranks should be unique
        ranks = [item["rank"] for item in ranked_items]
        assert len(ranks) == len(set(ranks)), f"Duplicate ranks: {ranks}"

# SPDX-License-Identifier: Apache-2.0
"""Sample queries and demo user profile for the demo experience.

Hardcoded queries curated for educational value — they work with any demo
dump that has the expected profile distribution from SP6.
"""
from __future__ import annotations

import click

DEMO_USER_PROFILE_DESCRIPTION = """\
Your demo profile is a composite Founder/CTO at a Bengaluru-based AI startup.
Eight years of experience spanning machine learning, product management, and
data engineering. Previously held senior roles at mid-stage startups and a
brief stint at a large tech company. Skills lean heavily toward ML/AI, with
secondary strength in product strategy and data infrastructure.

Affinity scores are calculated relative to this profile — connections who share
overlapping skills, similar seniority, or past company overlap will score
higher. This is why ML engineers and senior ICs tend to appear near the top."""

SAMPLE_QUERIES = [
    {
        "category": "search",
        "title": "Semantic Search",
        "query": "Who in my network has experience with distributed systems at a Series B startup?",
        "explanation": (
            "Semantic search understands intent, not just keywords. This finds "
            "people whose experience *means* distributed systems — even if their "
            "profile says 'infrastructure engineering' or 'scalability'."
        ),
        "followups": [
            "Tell me more about [name]'s background",
            "Who else has similar experience but in a different city?",
        ],
    },
    {
        "category": "affinity",
        "title": "Affinity & Relationships",
        "query": "Who are my strongest connections in ML?",
        "explanation": (
            "Affinity scores reflect shared skills, company overlap, and "
            "seniority proximity. Someone who worked at the same company AND "
            "shares your ML background scores higher than a distant connection "
            "with only one overlap."
        ),
        "followups": [
            "Why does [name] score higher than [name]?",
            "Who has the highest affinity but I haven't talked to recently?",
        ],
    },
    {
        "category": "agent",
        "title": "AI Agent",
        "query": "Compare the top 3 data scientists in my network for a founding engineer role",
        "explanation": (
            "The AI agent synthesizes profiles, affinity scores, and your "
            "requirements into a structured comparison. It reasons about fit, "
            "not just keyword matches."
        ),
        "followups": [
            "Draft a reachout message for [name]",
            "What would make [name] a better fit than [name]?",
        ],
    },
]


def format_demo_profile() -> str:
    """Return the demo user profile description formatted for terminal output."""
    lines = [
        click.style("  Your Demo Profile", bold=True),
        "",
    ]
    for line in DEMO_USER_PROFILE_DESCRIPTION.splitlines():
        lines.append(f"  {line}")
    return "\n".join(lines)


def format_sample_queries() -> str:
    """Return all sample queries formatted for terminal output."""
    lines = [
        "",
        click.style("  Sample Queries to Try", bold=True),
        "",
        "  Use these with the /linkedout skill in Claude Code or Codex:",
        "",
    ]

    for i, q in enumerate(SAMPLE_QUERIES, 1):
        category_label = click.style(f"[{q['title']}]", bold=True)
        lines.append(f"  {i}. {category_label}")
        lines.append(f"     {click.style(q['query'], fg='cyan')}")
        lines.append(f"     {q['explanation']}")
        if q["followups"]:
            lines.append("     Then try:")
            for followup in q["followups"]:
                lines.append(f"       -> {followup}")
        lines.append("")

    lines.append("  Tip: Run `linkedout demo-help` to see these again anytime.")
    return "\n".join(lines)

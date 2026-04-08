# SPDX-License-Identifier: Apache-2.0
"""20 calibration queries for LLM-as-judge benchmark validation."""

SPIKE_QUERIES = [
    # ── SJ persona (4) ──────────────────────────────────────────────────────
    {
        "id": "sj_01",
        "persona": "sj",
        "query": "Who are the strongest warm intro paths to someone at Stripe?",
        "tests": "Multi-hop reasoning, affinity scores, mutual connections",
    },
    {
        "id": "sj_02",
        "persona": "sj",
        "query": "Who do I know that transitioned from IC to management and might be a good mentor for someone making that switch?",
        "tests": "Career trajectory inference, role classification across history",
    },
    {
        "id": "sj_03",
        "persona": "sj",
        "query": "People in my network who are probably hiring right now — recently promoted to director+ or joined a startup that just raised funding",
        "tests": "Temporal reasoning, seniority classification, funding signal inference",
    },
    {
        "id": "sj_04",
        "persona": "sj",
        "query": "Find people who started in services companies but have been climbing fast at product companies — senior+ in under 3 years",
        "tests": "Multi-company trajectory, time-based career velocity",
    },
    # ── Recruiter persona (3) ────────────────────────────────────────────────
    {
        "id": "rec_01",
        "persona": "recruiter",
        "query": "ML engineers with 5+ years who've worked at both startups and big tech — likely open to a new role",
        "tests": "Multi-signal: skills + tenure + company type + job-switching inference",
    },
    {
        "id": "rec_02",
        "persona": "recruiter",
        "query": "Strong backend engineers in Bangalore who've stayed at their current company less than 2 years",
        "tests": "Location + skill + temporal retention filter",
    },
    {
        "id": "rec_03",
        "persona": "recruiter",
        "query": "People who've done engineering leadership at Series B-C startups",
        "tests": "Seniority + company stage inference from funding data",
    },
    # ── Founder persona (3) ──────────────────────────────────────────────────
    {
        "id": "fnd_01",
        "persona": "founder",
        "query": "Who in my network could be a technical co-founder for a developer tools startup?",
        "tests": "Role inference, skill matching, entrepreneurial signal detection",
    },
    {
        "id": "fnd_02",
        "persona": "founder",
        "query": "Connections who are active in the AI/ML space and have shipped products — not just researchers",
        "tests": "Semantic understanding, distinguishing practitioners from academics",
    },
    {
        "id": "fnd_03",
        "persona": "founder",
        "query": "People who've built and scaled engineering teams from 5 to 50+ at fast-growing companies",
        "tests": "Org-scaling inference from title progression + company growth signals",
    },
    # ── Extended set: temporal reasoning (2) ────────────────────────────────
    {
        "id": "sj_05",
        "persona": "sj",
        "query": "Who in my network switched jobs in the last 6 months and landed somewhere interesting?",
        "tests": "Temporal reasoning: recent job change detection via experience start_date",
    },
    {
        "id": "rec_04",
        "persona": "recruiter",
        "query": "Engineers who've been at their current company 3-5 years and are statistically due for a move",
        "tests": "Passive candidate inference from tenure duration without explicit signals",
    },
    # ── Extended set: seniority without title keywords (2) ──────────────────
    {
        "id": "sj_06",
        "persona": "sj",
        "query": "Who are the most influential people in my network in the fintech space, regardless of their title?",
        "tests": "Influence inference without relying on title seniority keywords — company prestige, network centrality, affinity",
    },
    {
        "id": "rec_05",
        "persona": "recruiter",
        "query": "Find principal-level engineers — people doing IC work at the highest level, not necessarily with that title",
        "tests": "Seniority inference without exact title match — look for scope of impact signals in headline/experience",
    },
    # ── Extended set: industry pivot signals (2) ─────────────────────────────
    {
        "id": "sj_07",
        "persona": "sj",
        "query": "People who made a successful pivot from enterprise software to consumer tech in the last 5 years",
        "tests": "Industry transition detection: sequence of companies across enterprise vs consumer verticals",
    },
    {
        "id": "fnd_04",
        "persona": "founder",
        "query": "Connections who've moved from large tech companies into climate or sustainability roles",
        "tests": "Domain pivot signal from company industry tagging or headline keywords",
    },
    # ── Extended set: passive vs active candidate signals (1) ────────────────
    {
        "id": "rec_06",
        "persona": "recruiter",
        "query": "People who look like they might be quietly exploring options — active on LinkedIn but haven't changed jobs recently",
        "tests": "Passive candidate signal inference without explicit job-seeking markers",
    },
    # ── Extended set: multi-hop network paths (1) ────────────────────────────
    {
        "id": "sj_08",
        "persona": "sj",
        "query": "Who should I talk to if I want a warm intro to someone at OpenAI or Anthropic?",
        "tests": "Multi-hop path reasoning through mutual connections at specific companies",
    },
    # ── Extended set: founder domain expertise (2) ───────────────────────────
    {
        "id": "fnd_05",
        "persona": "founder",
        "query": "Advisors or angels in my network who have operating experience at developer tools or infrastructure companies",
        "tests": "Role inference (advisor/angel) combined with domain expertise from career history",
    },
    {
        "id": "fnd_06",
        "persona": "founder",
        "query": "People in my network who've been early employees (first 20) at startups that reached Series C or beyond",
        "tests": "Early employee inference from join date vs company growth timeline, combined with funding stage data",
    },
]

# SPDX-License-Identifier: Apache-2.0
"""Unit tests for role classification functions.

Uses @pytest.mark.parametrize for exhaustive edge case coverage.
"""

import pytest

from dev_tools.classify_roles import classify_function, classify_seniority


# --- Seniority classification ---

@pytest.mark.parametrize("title,expected", [
    # C-Suite
    ("CEO", "c_suite"),
    ("Chief Technology Officer", "c_suite"),
    ("CTO & Co-Founder", "c_suite"),  # C-suite before founder
    # Founder
    ("Founder", "founder"),
    ("Co-Founder", "founder"),
    ("Co-founder & CEO", "c_suite"),  # C-suite checked first
    # VP
    ("VP of Engineering", "vp"),
    ("Senior Vice President", "vp"),
    ("SVP, Product", "vp"),
    ("AVP Operations", "vp"),
    # Director
    ("Director of Engineering", "director"),
    ("Head of Product", "director"),
    ("Senior Director", "director"),  # structural wins over modifier
    # Manager — structural, checked before Senior
    ("Engineering Manager", "manager"),
    ("Senior Engineering Manager", "manager"),  # manager before senior
    ("Product Manager", "manager"),
    ("Program Manager", "manager"),
    # Lead
    ("Tech Lead", "lead"),
    ("Principal Engineer", "lead"),
    ("Staff Software Engineer", "lead"),
    ("Solutions Architect", "lead"),
    ("Principal Product Manager", "manager"),  # manager before principal
    # Senior
    ("Senior Software Engineer", "senior"),
    ("Sr. Developer", "senior"),
    ("SSE", "senior"),
    ("SDE-2", "senior"),
    # Mid
    ("Software Engineer", "mid"),
    ("Data Analyst", "mid"),
    ("Business Analyst", "mid"),
    ("UX Designer", "mid"),
    # Junior
    ("Junior Developer", "junior"),
    ("Graduate Engineer", "junior"),
    ("Trainee", "junior"),
    # Intern
    ("Software Engineering Intern", "intern"),
    ("Summer Internship", "intern"),
    ("Co-op Student", "intern"),
    # None
    (None, None),
    ("", None),
    ("Board Member", None),  # not classified
    ("Freelancer", None),
])
def test_classify_seniority(title, expected):
    assert classify_seniority(title) == expected


# --- Function classification (ordered by specificity) ---

@pytest.mark.parametrize("title,expected", [
    # Data — before engineering
    ("Data Engineer", "data"),
    ("Data Scientist", "data"),  # data before research
    ("Machine Learning Engineer", "data"),
    ("AI Engineer", "data"),
    ("Business Intelligence Analyst", "data"),
    # Research
    ("Research Scientist", "research"),
    ("R&D Engineer", "research"),
    # Design — before product
    ("Product Designer", "design"),
    ("UX Designer", "design"),
    ("UI/UX Lead", "design"),
    # Product
    ("Product Manager", "product"),
    ("Product Owner", "product"),
    # Engineering — general catch-all
    ("Software Engineer", "engineering"),
    ("Backend Developer", "engineering"),
    ("DevOps Engineer", "engineering"),
    ("QA Engineer", "engineering"),
    ("Full Stack Developer", "engineering"),
    ("Platform Engineer", "engineering"),
    # Marketing
    ("Marketing Manager", "marketing"),
    ("Growth Lead", "marketing"),
    ("Content Strategist", "marketing"),
    # Sales
    ("Account Executive", "sales"),
    ("Business Development Rep", "sales"),
    # Finance
    ("Financial Analyst", "finance"),
    ("Controller", "finance"),
    # HR
    ("Recruiter", "hr"),
    ("Talent Acquisition", "hr"),
    ("People Operations Manager", "hr"),
    # Operations
    ("Operations Manager", "operations"),
    ("Supply Chain Analyst", "operations"),
    # Consulting
    ("Management Consultant", "consulting"),
    ("Strategy Advisor", "consulting"),
    # None
    (None, None),
    ("", None),
    ("CEO", None),  # seniority-only title, no function match
])
def test_classify_function(title, expected):
    assert classify_function(title) == expected

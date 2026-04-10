# SPDX-License-Identifier: Apache-2.0
"""One-time curation script to generate synthetic test data fixtures.

Generates version-controlled CSV fixtures for E2E integration tests.
The fixtures are pre-generated and checked in — this script exists
for reproducibility and documentation of the selection criteria.

Output:
    tests/e2e/fixtures/linkedin-connections-subset.csv  (15 rows)
    tests/e2e/fixtures/gmail-contacts-subset.csv        (10 rows)

Usage:
    python -m dev_tools.curate_test_data
    python -m dev_tools.curate_test_data --verify
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "tests" / "e2e" / "fixtures"

# ── LinkedIn connections (synthetic) ──────────────────────────────────
# Selection criteria:
#   - 9 different companies (Google, Meta, Stripe, Amazon, Notion,
#     Microsoft, Anthropic, Figma, Salesforce)
#   - Role diversity: IC, management, leadership, product, design
#   - Temporal diversity: 2018-2025
#   - Name diversity: varied first/last names
#
# Format matches backend/src/linkedout/import_pipeline/converters/linkedin_csv.py:
#   First Name, Last Name, URL, Email Address, Company, Position, Connected On
#   Date format: DD Mon YYYY

LINKEDIN_PREAMBLE = [
    'Notes:,"This file contains synthetic test data for LinkedOut integration tests."',
    'Notes:,"Connections are listed in reverse chronological order."',
    "",
]

LINKEDIN_HEADER = ["First Name", "Last Name", "URL", "Email Address", "Company", "Position", "Connected On"]

LINKEDIN_ROWS = [
    ["Wei", "Zhang", "https://www.linkedin.com/in/weizhang", "", "Anthropic", "ML Engineer", "30 Jan 2025"],
    ["Nathan", "Williams", "https://www.linkedin.com/in/nathanwilliams", "nathan.w@example.com", "Notion", "CTO", "01 Jul 2024"],
    ["Sarah", "Chen", "https://www.linkedin.com/in/sarahchen", "", "Google", "Software Engineer", "15 Jan 2024"],
    ["Lisa", "Thompson", "https://www.linkedin.com/in/lisathompson", "", "Anthropic", "Research Scientist", "28 Nov 2023"],
    ["Tomás", "Silva", "https://www.linkedin.com/in/tomassilva", "", "Stripe", "Backend Engineer", "09 May 2023"],
    ["James", "Rodriguez", "https://www.linkedin.com/in/jamesrodriguez", "james.r@example.com", "Meta", "Product Manager", "03 Mar 2023"],
    ["Aisha", "Hassan", "https://www.linkedin.com/in/aishahassan", "", "Figma", "Product Designer", "05 Dec 2022"],
    ["Priya", "Patel", "https://www.linkedin.com/in/priyapatel", "", "Stripe", "Engineering Manager", "22 Jul 2022"],
    ["David", "Kim", "https://www.linkedin.com/in/davidkim", "", "Amazon", "Senior Software Engineer", "11 Sep 2021"],
    ["Carlos", "Gomez", "https://www.linkedin.com/in/carlosgomez", "", "Amazon", "Data Engineer", "17 Aug 2021"],
    ["Emily", "Watson", "https://www.linkedin.com/in/emilywatson", "emily.w@example.com", "Notion", "Staff Engineer", "08 Feb 2024"],
    ["Jennifer", "Park", "https://www.linkedin.com/in/jenniferpark", "", "Meta", "Technical Program Manager", "23 Oct 2020"],
    ["Raj", "Mehta", "https://www.linkedin.com/in/rajmehta", "", "Microsoft", "Principal Engineer", "19 Jun 2020"],
    ["Michael", "O'Brien", "https://www.linkedin.com/in/michaelobrien", "", "Google", "VP Engineering", "14 Apr 2019"],
    ["Keiko", "Tanaka", "https://www.linkedin.com/in/keikotanaka", "", "Salesforce", "Solutions Architect", "12 Mar 2018"],
]

# ── Gmail contacts (synthetic, google_job format) ────────────────────
# Selection criteria:
#   - 4 contacts match LinkedIn names (Sarah Chen, Raj Mehta,
#     Lisa Thompson, Emily Watson) — tests affinity overlap
#   - 6 contacts have no LinkedIn match — tests no-match handling
#
# Format matches backend/src/linkedout/import_pipeline/converters/google_job.py:
#   Given Name, Family Name, Name, E-mail 1 - Value, Group Membership
#
# NOTE: The `linkedout import-contacts` CLI command expects a directory
# with three files (contacts_from_google_job.csv, contacts_with_phone.csv,
# gmail_contacts_email_id_only.csv). This single fixture uses the
# google_job format. The integration test harness (SP-D) should either:
#   (a) copy this file as contacts_from_google_job.csv and create empty
#       stubs for the other two, or
#   (b) use the converter registry directly to parse this file.

GMAIL_HEADER = ["Given Name", "Family Name", "Name", "E-mail 1 - Value", "Group Membership"]

GMAIL_ROWS = [
    # Overlap with LinkedIn subset (4 contacts)
    ["Sarah", "Chen", "Sarah Chen", "sarah.chen@gmail.com", "* myContacts"],
    ["Raj", "Mehta", "Raj Mehta", "raj.mehta@outlook.com", "* myContacts"],
    ["Lisa", "Thompson", "Lisa Thompson", "lisa.t@gmail.com", "* myContacts"],
    ["Emily", "Watson", "Emily Watson", "emily.w@gmail.com", "* myContacts"],
    # No LinkedIn match (6 contacts)
    ["Alex", "Rivera", "Alex Rivera", "alex.rivera@gmail.com", "* myContacts"],
    ["Maria", "Santos", "Maria Santos", "maria.santos@yahoo.com", "* myContacts"],
    ["Ben", "Foster", "Ben Foster", "bfoster@hotmail.com", "* myContacts"],
    ["Nina", "Petrova", "Nina Petrova", "nina.p@protonmail.com", "* myContacts"],
    ["Omar", "Farooq", "Omar Farooq", "omar.farooq@gmail.com", "* myContacts"],
    ["Yuki", "Sato", "Yuki Sato", "yuki.sato@outlook.com", "* myContacts"],
]


def write_linkedin_csv(output_path: Path) -> int:
    """Write the LinkedIn connections fixture CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        for line in LINKEDIN_PREAMBLE:
            f.write(line + "\n")

        writer = csv.writer(f)
        writer.writerow(LINKEDIN_HEADER)
        writer.writerows(LINKEDIN_ROWS)

    return len(LINKEDIN_ROWS)


def write_gmail_csv(output_path: Path) -> int:
    """Write the Gmail contacts fixture CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(GMAIL_HEADER)
        writer.writerows(GMAIL_ROWS)

    return len(GMAIL_ROWS)


def verify_linkedin(path: Path) -> list[str]:
    """Verify the LinkedIn fixture meets selection criteria."""
    errors = []
    if not path.exists():
        return [f"File not found: {path}"]

    with open(path, encoding="utf-8") as f:
        text = f.read()

    # Find header row (skip preamble)
    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if "First Name" in line and "Last Name" in line and "URL" in line:
            header_idx = i
            break

    if header_idx is None:
        return ["Could not find header row"]

    csv_text = "\n".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    if not (10 <= len(rows) <= 20):
        errors.append(f"Expected 10-20 rows, got {len(rows)}")

    companies = {r["Company"] for r in rows if r.get("Company")}
    if len(companies) < 8:
        errors.append(f"Expected 8+ companies, got {len(companies)}: {companies}")

    positions = {r["Position"] for r in rows if r.get("Position")}
    role_categories = set()
    for pos in positions:
        pos_lower = pos.lower()
        if any(w in pos_lower for w in ["engineer", "developer", "architect"]):
            role_categories.add("engineering")
        elif "manager" in pos_lower and "engineer" not in pos_lower:
            role_categories.add("management")
        elif any(w in pos_lower for w in ["product", "program"]):
            role_categories.add("product")
        elif any(w in pos_lower for w in ["vp", "cto", "ceo", "director"]):
            role_categories.add("leadership")
        elif any(w in pos_lower for w in ["designer", "researcher", "scientist"]):
            role_categories.add("other")

    if len(role_categories) < 3:
        errors.append(f"Expected 3+ role categories, got {len(role_categories)}: {role_categories}")

    return errors


def verify_gmail(path: Path, linkedin_path: Path) -> list[str]:
    """Verify the Gmail fixture meets selection criteria."""
    errors = []
    if not path.exists():
        return [f"File not found: {path}"]

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        gmail_rows = list(reader)

    if not (10 <= len(gmail_rows) <= 15):
        errors.append(f"Expected 10-15 rows, got {len(gmail_rows)}")

    # Check overlap with LinkedIn
    linkedin_names: set[str] = set()
    if linkedin_path.exists():
        with open(linkedin_path, encoding="utf-8") as f:
            text = f.read()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "First Name" in line and "Last Name" in line:
                csv_text = "\n".join(lines[i:])
                for row in csv.DictReader(io.StringIO(csv_text)):
                    name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
                    if name:
                        linkedin_names.add(name.lower())
                break

    gmail_names = {r.get("Name", "").strip().lower() for r in gmail_rows if r.get("Name")}
    overlap = gmail_names & linkedin_names
    no_match = gmail_names - linkedin_names

    if len(overlap) < 3:
        errors.append(f"Expected 3+ LinkedIn matches, got {len(overlap)}: {overlap}")
    if len(no_match) < 3:
        errors.append(f"Expected 3+ non-matches, got {len(no_match)}: {no_match}")

    return errors


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate or verify E2E test data fixtures")
    parser.add_argument("--verify", action="store_true", help="Verify existing fixtures instead of regenerating")
    args = parser.parse_args()

    linkedin_path = FIXTURES_DIR / "linkedin-connections-subset.csv"
    gmail_path = FIXTURES_DIR / "gmail-contacts-subset.csv"

    if args.verify:
        print("Verifying fixtures...")
        all_errors = []

        print(f"\n  LinkedIn: {linkedin_path}")
        errors = verify_linkedin(linkedin_path)
        if errors:
            for e in errors:
                print(f"    FAIL: {e}")
            all_errors.extend(errors)
        else:
            print("    PASS")

        print(f"\n  Gmail: {gmail_path}")
        errors = verify_gmail(gmail_path, linkedin_path)
        if errors:
            for e in errors:
                print(f"    FAIL: {e}")
            all_errors.extend(errors)
        else:
            print("    PASS")

        if all_errors:
            print(f"\n{len(all_errors)} verification errors found.")
            sys.exit(1)
        else:
            print("\nAll fixtures verified successfully.")
        return

    # Generate fixtures
    print("Generating test data fixtures...")

    n = write_linkedin_csv(linkedin_path)
    print(f"  LinkedIn: {n} connections -> {linkedin_path}")

    n = write_gmail_csv(gmail_path)
    print(f"  Gmail:    {n} contacts   -> {gmail_path}")

    # Run verification on generated output
    print("\nVerifying generated fixtures...")
    errors = verify_linkedin(linkedin_path) + verify_gmail(gmail_path, linkedin_path)
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        sys.exit(1)
    else:
        print("  All checks passed.")


if __name__ == "__main__":
    main()

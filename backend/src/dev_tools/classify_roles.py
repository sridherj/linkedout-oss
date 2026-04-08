# SPDX-License-Identifier: Apache-2.0
"""Classify LinkedIn job titles into seniority levels and function areas.

Uses regex-based first-match-wins strategy, ordered by structural seniority
and function specificity.

Also provides main() for bulk DB operations: extract titles, classify,
upsert role_alias, and backfill experience + crawled_profile tables.
"""

import re
from collections import Counter

import click
from sqlalchemy import text

from dev_tools.db.fixed_data import SYSTEM_USER_ID
from shared.common.nanoids import Nanoid
from shared.infra.db.db_session_manager import DbSessionType, db_session_manager

# --- Seniority classification: first-match-wins, ordered by structural seniority ---

SENIORITY_RULES = [
    ("c_suite", re.compile(
        r"\b(?:ceo|cto|cfo|coo|cio|ciso|cmo|cpo|chief\s+\w+\s+officer)\b", re.I)),
    ("founder", re.compile(
        r"\b(?:co-?\s*founder|founder)\b", re.I)),
    ("vp", re.compile(
        r"\b(?:vp|vice\s+president|evp|svp|avp)\b", re.I)),
    ("director", re.compile(
        r"\b(?:director|head\s+of)\b", re.I)),
    ("manager", re.compile(
        r"\b(?:manager|engineering\s+manager|product\s+manager|program\s+manager)\b", re.I)),
    ("lead", re.compile(
        r"\b(?:lead|principal|staff|architect)\b", re.I)),
    ("senior", re.compile(
        r"\b(?:senior|sr\.?|sse|sde[\s-]*[23]|sde[\s-]*ii|senior\s+member)\b", re.I)),
    ("junior", re.compile(
        r"\b(?:junior|jr\.?|entry[\s-]*level|trainee|graduate|fresher)\b", re.I)),
    ("intern", re.compile(
        r"\b(?:intern|internship|co[\s-]*op|apprentice)\b", re.I)),
    ("mid", re.compile(
        r"\b(?:engineer|developer|analyst|consultant|specialist|associate|designer|scientist)\b", re.I)),
]


def classify_seniority(title: str | None) -> str | None:
    """Classify a job title into a seniority level. First match wins."""
    if not title:
        return None
    for level, pattern in SENIORITY_RULES:
        if pattern.search(title):
            return level
    return None


# --- Function classification: first-match-wins, ordered by specificity ---

FUNCTION_RULES = [
    ("data", re.compile(
        r"\b(?:data|analytics|bi\b|business\s+intelligence|machine\s+learning|ml\b|ai\b|artificial\s+intelligence)", re.I)),
    ("research", re.compile(
        r"\b(?:research|r&d|scientist)", re.I)),
    ("design", re.compile(
        r"\b(?:design|ux|ui\b|user\s+experience|user\s+interface|graphic|visual)", re.I)),
    ("product", re.compile(
        r"\b(?:product\s+manag|product\s+own|product\s+lead|product\s+director|pm\b)", re.I)),
    ("engineering", re.compile(
        r"\b(?:engineer|developer|software|swe\b|sde\b|devops|infrastructure|backend|frontend|fullstack|full[\s-]*stack|platform|systems|cloud|security|qa\b|quality|test|automation)", re.I)),
    ("marketing", re.compile(
        r"\b(?:marketing|growth|brand|content|seo\b|sem\b|digital\s+marketing|communications)", re.I)),
    ("sales", re.compile(
        r"\b(?:sales|account\s+executive|business\s+development|bdr\b|sdr\b|revenue|partnerships)", re.I)),
    ("finance", re.compile(
        r"\b(?:finance|accounting|controller|treasury|tax\b|audit|financial)", re.I)),
    ("hr", re.compile(
        r"\b(?:human\s+resources|hr\b|talent|recruiting|recruiter|people\s+ops|people\s+operations)", re.I)),
    ("operations", re.compile(
        r"\b(?:operations|ops\b|supply\s+chain|logistics|procurement|facilities)", re.I)),
    ("consulting", re.compile(
        r"\b(?:consult|advisory|strategy)", re.I)),
]


def classify_function(title: str | None) -> str | None:
    """Classify a job title into a function area. First match wins."""
    if not title:
        return None
    for area, pattern in FUNCTION_RULES:
        if pattern.search(title):
            return area
    return None


BATCH_SIZE = 500


def main(dry_run: bool = False) -> int:
    """Classify all titles and populate role_alias, experience, and crawled_profile.

    Returns 0 on success, 1 on failure.
    """
    try:
        with db_session_manager.get_session(DbSessionType.WRITE, app_user_id=SYSTEM_USER_ID) as session:
            # Step 1: Extract distinct titles
            rows = session.execute(text("""
                SELECT DISTINCT title FROM (
                    SELECT position AS title FROM experience WHERE position IS NOT NULL
                    UNION
                    SELECT current_position AS title FROM crawled_profile WHERE current_position IS NOT NULL
                ) t
            """)).fetchall()

            titles = [r[0] for r in rows]
            if not titles:
                click.echo("No titles found")
                return 0

            click.echo(f"Found {len(titles)} distinct titles")

            # Step 2: In-memory classification
            classifications = []
            for raw_title in titles:
                normalized = raw_title.strip().lower()
                seniority = classify_seniority(normalized)
                function = classify_function(normalized)
                classifications.append({
                    "title": raw_title,
                    "alias_title": normalized,
                    "canonical_title": normalized,
                    "seniority_level": seniority,
                    "function_area": function,
                })

            classified = [c for c in classifications if c["seniority_level"] or c["function_area"]]
            seniority_dist = Counter(c["seniority_level"] for c in classifications if c["seniority_level"])
            function_dist = Counter(c["function_area"] for c in classifications if c["function_area"])

            click.echo(f"Classified: {len(classified)}/{len(classifications)} ({100*len(classified)//len(classifications)}%)")
            click.echo(f"\nSeniority distribution:")
            for level, count in seniority_dist.most_common():
                click.echo(f"  {level}: {count}")
            click.echo(f"\nFunction distribution:")
            for area, count in function_dist.most_common():
                click.echo(f"  {area}: {count}")

            if dry_run:
                click.echo("\nDry run — no DB writes performed.")
                return 0

            # Step 3: INSERT role_alias with ON CONFLICT
            insert_sql = text("""
                INSERT INTO role_alias (id, alias_title, canonical_title, seniority_level, function_area, is_active, version, created_at, updated_at)
                VALUES (:id, :alias_title, :canonical_title, :seniority_level, :function_area, true, 1, NOW(), NOW())
                ON CONFLICT (alias_title) DO UPDATE SET
                    seniority_level = EXCLUDED.seniority_level,
                    function_area = EXCLUDED.function_area,
                    updated_at = NOW()
            """)

            for i in range(0, len(classifications), BATCH_SIZE):
                batch = classifications[i:i + BATCH_SIZE]
                params = [
                    {
                        "id": Nanoid.make_nanoid_with_prefix("ra"),
                        "alias_title": c["alias_title"],
                        "canonical_title": c["canonical_title"],
                        "seniority_level": c["seniority_level"],
                        "function_area": c["function_area"],
                    }
                    for c in batch
                ]
                session.execute(insert_sql, params)

            ra_count = session.execute(text("SELECT COUNT(*) FROM role_alias")).scalar()
            click.echo(f"\nrole_alias rows: {ra_count}")

            # Step 4: UPDATE experience via temp table JOIN
            session.execute(text("CREATE TEMP TABLE _role_map (title TEXT, seniority TEXT, function_area TEXT)"))

            temp_insert = text("INSERT INTO _role_map (title, seniority, function_area) VALUES (:title, :seniority, :function_area)")
            for i in range(0, len(classifications), BATCH_SIZE):
                batch = classifications[i:i + BATCH_SIZE]
                params = [
                    {"title": c["title"], "seniority": c["seniority_level"], "function_area": c["function_area"]}
                    for c in batch
                ]
                session.execute(temp_insert, params)

            result = session.execute(text("""
                UPDATE experience e
                SET seniority_level = rm.seniority,
                    function_area = rm.function_area
                FROM _role_map rm
                WHERE e.position = rm.title
                  AND (e.seniority_level IS NULL OR e.function_area IS NULL)
            """))
            exp_updated = result.rowcount
            click.echo(f"Experience rows updated: {exp_updated}")

            session.execute(text("DROP TABLE IF EXISTS _role_map"))

            # Step 5: UPDATE crawled_profile from current experience
            result = session.execute(text("""
                UPDATE crawled_profile p
                SET seniority_level = sub.seniority_level,
                    function_area = sub.function_area
                FROM (
                    SELECT DISTINCT ON (crawled_profile_id)
                        crawled_profile_id, seniority_level, function_area
                    FROM experience
                    WHERE is_current = TRUE
                      AND (seniority_level IS NOT NULL OR function_area IS NOT NULL)
                    ORDER BY crawled_profile_id, start_date DESC NULLS LAST, id DESC
                ) sub
                WHERE sub.crawled_profile_id = p.id
                  AND p.has_enriched_data = TRUE
            """))
            cp_from_exp = result.rowcount
            click.echo(f"Profiles updated from experience: {cp_from_exp}")

            # Step 5b: Direct role_alias fallback
            result = session.execute(text("""
                UPDATE crawled_profile p
                SET seniority_level = ra.seniority_level,
                    function_area = ra.function_area
                FROM role_alias ra
                WHERE ra.alias_title = p.current_position
                  AND p.seniority_level IS NULL
                  AND p.current_position IS NOT NULL
            """))
            cp_from_ra = result.rowcount
            click.echo(f"Profiles updated from role_alias fallback: {cp_from_ra}")

            # Step 6: Summary
            click.echo(f"\n=== Summary ===")
            click.echo(f"Titles processed: {len(classifications)}")
            click.echo(f"role_alias rows: {ra_count}")
            click.echo(f"Experience rows updated: {exp_updated}")
            click.echo(f"Profiles updated (experience): {cp_from_exp}")
            click.echo(f"Profiles updated (role_alias fallback): {cp_from_ra}")

        return 0

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return 1

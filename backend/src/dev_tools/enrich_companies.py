# SPDX-License-Identifier: Apache-2.0
"""Enrich company records via PDL CSV scan + Wikidata SPARQL gap-fill.

Two-phase enrichment waterfall:
  Phase A: PDL CSV scan — match by LinkedIn slug then fallback by name
  Phase B: Wikidata SPARQL gap-fill — fill remaining gaps for industry/website/HQ

Each phase runs in a separate DB transaction. PDL commits first so its data
persists even if Wikidata fails. Uses COALESCE semantics to never overwrite
existing data. Idempotent via enrichment_sources array check.
"""

import csv
import os
import re
import time
from pathlib import Path
from typing import Optional

import click
import httpx
from sqlalchemy import text

from dev_tools.company_utils import compute_size_tier, normalize_company_name
from dev_tools.wikidata_utils import (
    SEARCH_DELAY,
    batch_sparql_metadata,
    wikidata_search,
)
from shared.infra.db.cli_db import cli_db_manager
from shared.infra.db.db_session_manager import DbSessionType
from shared.utilities.logger import get_logger

logger = get_logger(__name__, component="cli")

# ---------------------------------------------------------------------------
# PDL constants
# ---------------------------------------------------------------------------

PDL_SIZE_MAP: dict[str, int] = {
    "1-10": 5,
    "11-50": 30,
    "51-200": 125,
    "201-500": 350,
    "501-1000": 750,
    "1001-5000": 3000,
    "5001-10000": 7500,
    "10001+": 15000,
}

PDL_COLUMNS = [
    "id",
    "name",
    "size",
    "industry",
    "website",
    "linkedin_url",
    "founded",
    "location_locality",
    "location_country",
    "employee_count",
]

_YEAR_RE = re.compile(r"((?:19|20)\d{2})")


def _parse_founded(val: str) -> Optional[int]:
    """Extract a 4-digit year from a PDL founded field."""
    if not val:
        return None
    m = _YEAR_RE.search(val)
    return int(m.group(1)) if m else None


_SLUG_RE = re.compile(r"linkedin\.com/company/([^/?#]+)")


def _extract_slug(url: str) -> Optional[str]:
    """Extract the company slug from a LinkedIn URL."""
    if not url:
        return None
    m = _SLUG_RE.search(url)
    return m.group(1).lower().strip("/") if m else None




def _domain_from_website(url: str) -> Optional[str]:
    """Extract bare domain from a website URL."""
    if not url:
        return None
    url = url.lower().strip()
    for prefix in ("https://", "http://", "www."):
        if url.startswith(prefix):
            url = url[len(prefix):]
    return url.split("/")[0] or None


# ---------------------------------------------------------------------------
# PDL Phase (Phase A)
# ---------------------------------------------------------------------------

def _get_pdl_index_path(pdl_path: str) -> str:
    """Return the SQLite index path for a PDL CSV (sibling file, .sqlite extension)."""
    return pdl_path.rsplit(".", 1)[0] + ".sqlite"


def build_pdl_index(pdl_path: str) -> str:
    """Build a SQLite index from the PDL CSV. Returns the index path.

    Indexes by linkedin slug and lowercase company name for fast lookups.
    Only runs if the index doesn't exist or is older than the CSV.
    """
    import sqlite3 as sqlite3_mod

    index_path = _get_pdl_index_path(pdl_path)

    # Skip if index is fresh
    if os.path.exists(index_path) and os.path.getmtime(index_path) >= os.path.getmtime(pdl_path):
        logger.info("PDL index exists and is fresh: %s", index_path)
        return index_path

    click.echo(f"Building PDL SQLite index (one-time, ~5 min for 34M rows)...")
    conn = sqlite3_mod.connect(index_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pdl_companies (
            slug TEXT,
            name_lower TEXT,
            pdl_id TEXT,
            industry TEXT,
            website TEXT,
            founded TEXT,
            country TEXT,
            locality TEXT,
            size TEXT
        )
    """)
    conn.execute("DELETE FROM pdl_companies")

    chunk_size = 50_000
    total = 0
    with open(pdl_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            slug = _extract_slug(row.get("linkedin_url", ""))
            name = (row.get("name") or "").strip().lower()
            batch.append((
                slug, name,
                row.get("id", ""),
                row.get("industry", ""),
                row.get("website", ""),
                row.get("founded", ""),
                row.get("country", ""),
                row.get("locality", ""),
                row.get("size", ""),
            ))
            if len(batch) >= chunk_size:
                conn.executemany(
                    "INSERT INTO pdl_companies VALUES (?,?,?,?,?,?,?,?,?)", batch
                )
                total += len(batch)
                batch.clear()
                if total % 500_000 == 0:
                    click.echo(f"  Indexed {total:,} rows...")

        if batch:
            conn.executemany(
                "INSERT INTO pdl_companies VALUES (?,?,?,?,?,?,?,?,?)", batch
            )
            total += len(batch)

    click.echo(f"  Creating indexes on slug and name...")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_slug ON pdl_companies(slug) WHERE slug != ''")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_name ON pdl_companies(name_lower) WHERE name_lower != ''")
    conn.commit()
    conn.close()
    click.echo(f"  PDL index built: {total:,} rows → {index_path}")
    return index_path


def load_pdl_matches_indexed(
    pdl_path: str,
    target_slugs: dict[str, str],
    target_names: dict[str, str],
) -> dict[str, dict]:
    """Look up target companies via JOIN against SQLite index.

    Loads target slugs/names into a temp table, then JOINs against the
    36M-row PDL index in two passes (slug match, then name fallback).
    Returns {company_id: {pdl_fields...}}.
    """
    import sqlite3 as sqlite3_mod

    index_path = build_pdl_index(pdl_path)
    conn = sqlite3_mod.connect(index_path)
    conn.row_factory = sqlite3_mod.Row

    # Load targets into temp tables for JOIN
    click.echo("  Loading targets into SQLite for JOIN...")
    conn.execute("CREATE TEMP TABLE target_slugs (slug TEXT PRIMARY KEY, company_id TEXT)")
    conn.execute("CREATE TEMP TABLE target_names (name_lower TEXT PRIMARY KEY, company_id TEXT)")
    conn.executemany(
        "INSERT OR IGNORE INTO target_slugs VALUES (?, ?)",
        [(s, cid) for s, cid in target_slugs.items() if s],
    )
    conn.executemany(
        "INSERT OR IGNORE INTO target_names VALUES (?, ?)",
        [(n, cid) for n, cid in target_names.items() if n],
    )
    click.echo(f"    {len(target_slugs)} slugs, {len(target_names)} names loaded")

    matches: dict[str, dict] = {}

    # Phase 1: slug JOIN
    click.echo("  Matching by LinkedIn slug (JOIN)...")
    rows = conn.execute("""
        SELECT ts.company_id, p.*
        FROM target_slugs ts
        JOIN pdl_companies p ON p.slug = ts.slug
    """).fetchall()
    for row in rows:
        cid = row["company_id"]
        if cid not in matches:
            matches[cid] = _row_to_pdl_fields(row)
    click.echo(f"    Slug matches: {len(matches)}")

    # Phase 2: name JOIN (skip already-matched companies)
    click.echo("  Matching by company name (JOIN)...")
    matched_ids = set(matches.keys())
    rows = conn.execute("""
        SELECT tn.company_id, p.*
        FROM target_names tn
        JOIN pdl_companies p ON p.name_lower = tn.name_lower
    """).fetchall()
    name_matched = 0
    for row in rows:
        cid = row["company_id"]
        if cid not in matches:
            matches[cid] = _row_to_pdl_fields(row)
            name_matched += 1
    click.echo(f"    Name matches: {name_matched}")

    conn.close()
    logger.info("PDL indexed lookup: %d total matches (slug + name)", len(matches))
    return matches


def _row_to_pdl_fields(row) -> dict:
    """Convert a SQLite row to PDL enrichment fields."""
    size_str = (row["size"] or "").strip()
    employee_count = PDL_SIZE_MAP.get(size_str)

    return {
        "pdl_id": row["pdl_id"] or None,
        "industry": row["industry"] or None,
        "website": row["website"] or None,
        "domain": _domain_from_website(row["website"] or ""),
        "founded_year": _parse_founded(row["founded"] or ""),
        "hq_city": row["locality"] or None,
        "hq_country": row["country"] or None,
        "employee_count_range": size_str or None,
        "estimated_employee_count": employee_count,
        "size_tier": compute_size_tier(employee_count),
    }


def _sanitize(val):
    """Strip NUL bytes from strings (PostgreSQL rejects them)."""
    if isinstance(val, str):
        return val.replace("\x00", "")
    return val


def apply_pdl_enrichment(session, company_id: str, fields: dict) -> bool:
    """UPDATE a company row with PDL data using COALESCE (never overwrite)."""
    fields = {k: _sanitize(v) for k, v in fields.items()}
    result = session.execute(
        text("""
            UPDATE company SET
                industry = COALESCE(industry, :industry),
                website = COALESCE(website, :website),
                domain = COALESCE(domain, :domain),
                founded_year = COALESCE(founded_year, :founded_year),
                hq_city = COALESCE(hq_city, :hq_city),
                hq_country = COALESCE(hq_country, :hq_country),
                employee_count_range = COALESCE(employee_count_range, :employee_count_range),
                estimated_employee_count = COALESCE(estimated_employee_count, :estimated_employee_count),
                size_tier = COALESCE(size_tier, :size_tier),
                pdl_id = COALESCE(pdl_id, :pdl_id),
                enrichment_sources = array_append(
                    CASE WHEN enrichment_sources IS NULL THEN ARRAY[]::text[] ELSE enrichment_sources END,
                    'pdl'
                ),
                enriched_at = NOW()
            WHERE id = :company_id
              AND (enrichment_sources IS NULL OR NOT ('pdl' = ANY(enrichment_sources)))
        """),
        {
            "company_id": company_id,
            "industry": fields.get("industry"),
            "website": fields.get("website"),
            "domain": fields.get("domain"),
            "founded_year": fields.get("founded_year"),
            "hq_city": fields.get("hq_city"),
            "hq_country": fields.get("hq_country"),
            "employee_count_range": fields.get("employee_count_range"),
            "estimated_employee_count": fields.get("estimated_employee_count"),
            "size_tier": fields.get("size_tier"),
            "pdl_id": fields.get("pdl_id"),
        },
    )
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Wikidata Phase (Phase B)
# ---------------------------------------------------------------------------

def run_wikidata_gapfill(session, limit: int = 500) -> int:
    """Query companies missing fields, search Wikidata, batch-fetch metadata."""
    rows = session.execute(
        text("""
            SELECT id, canonical_name FROM company
            WHERE (industry IS NULL OR website IS NULL)
              AND (enrichment_sources IS NULL OR NOT ('wikidata' = ANY(enrichment_sources)))
            ORDER BY network_connection_count DESC NULLS LAST
            LIMIT :limit
        """),
        {"limit": limit},
    ).fetchall()

    if not rows:
        logger.info("Wikidata gap-fill: no eligible companies found")
        return 0

    logger.info("Wikidata gap-fill: %d companies to search", len(rows))

    qid_map: dict[str, str] = {}  # qid -> company_id
    client = httpx.Client(timeout=30.0)

    try:
        for company_id, name in rows:
            result = wikidata_search(client, name)
            if result and result.get("qid"):
                qid_map[result["qid"]] = company_id
            time.sleep(SEARCH_DELAY)

        if not qid_map:
            logger.info("Wikidata gap-fill: no QIDs found")
            return 0

        logger.info("Wikidata gap-fill: %d QIDs found, fetching metadata", len(qid_map))
        metadata = batch_sparql_metadata(client, list(qid_map.keys()))
    finally:
        client.close()

    enriched_count = 0
    for qid, company_id in qid_map.items():
        meta = metadata.get(qid)
        if not meta:
            continue

        founded_year = None
        if meta.get("founded"):
            founded_year = _parse_founded(meta["founded"])

        employee_count = None
        if meta.get("employees"):
            try:
                employee_count = int(float(meta["employees"]))
            except (ValueError, TypeError):
                pass

        try:
            result = session.execute(
                text("""
                    UPDATE company SET
                        industry = COALESCE(industry, :industry),
                        website = COALESCE(website, :website),
                        founded_year = COALESCE(founded_year, :founded_year),
                        hq_city = COALESCE(hq_city, :hq_city),
                        estimated_employee_count = COALESCE(estimated_employee_count, :estimated_employee_count),
                        size_tier = COALESCE(size_tier, :size_tier),
                        wikidata_id = COALESCE(wikidata_id, :wikidata_id),
                        enrichment_sources = array_append(
                            CASE WHEN enrichment_sources IS NULL THEN ARRAY[]::text[] ELSE enrichment_sources END,
                            'wikidata'
                        ),
                        enriched_at = NOW()
                    WHERE id = :company_id
                      AND (enrichment_sources IS NULL OR NOT ('wikidata' = ANY(enrichment_sources)))
                """),
                {
                    "company_id": company_id,
                    "industry": meta.get("industry") or None,
                    "website": meta.get("website") or None,
                    "founded_year": founded_year,
                    "hq_city": meta.get("hq") or None,
                    "estimated_employee_count": employee_count,
                    "size_tier": compute_size_tier(employee_count),
                    "wikidata_id": qid,
                },
            )
            if result.rowcount > 0:
                enriched_count += 1
        except Exception:
            logger.warning("Wikidata update failed for company %s (QID %s)", company_id, qid, exc_info=True)

    logger.info("Wikidata gap-fill: enriched %d companies", enriched_count)
    return enriched_count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

@click.command("enrich-companies")
@click.option("--dry-run", is_flag=True, help="Print stats without modifying DB")
@click.option("--skip-wikidata", is_flag=True, help="Skip Wikidata gap-fill phase")
@click.option("--pdl-file", required=True, type=click.Path(exists=False), help="Path to PDL company CSV")
@click.option("--wikidata-limit", default=500, type=int, help="Max companies for Wikidata gap-fill")
@click.option("--force", is_flag=True, help="Re-enrich companies that already have PDL data")
def main(dry_run: bool, skip_wikidata: bool, pdl_file: str, wikidata_limit: int, force: bool) -> int:
    """Enrich company records from PDL CSV + Wikidata SPARQL."""
    db_manager = cli_db_manager()
    pdl_path = Path(pdl_file)
    if not pdl_path.exists():
        click.echo(f"PDL file not found: {pdl_file}. Download from People Data Labs free dataset.", err=True)
        return 1

    # --- Gather targets ---
    with db_manager.get_session(DbSessionType.WRITE) as session:
        if force:
            target_rows = session.execute(
                text("SELECT id, universal_name, canonical_name FROM company")
            ).fetchall()
        else:
            target_rows = session.execute(
                text("""
                    SELECT id, universal_name, canonical_name FROM company
                    WHERE enrichment_sources IS NULL
                       OR NOT ('pdl' = ANY(enrichment_sources))
                """)
            ).fetchall()

    if not target_rows:
        click.echo("No companies need enrichment.")
        return 0

    # Build lookup maps
    slug_to_id: dict[str, str] = {}
    name_to_id: dict[str, str] = {}
    for row in target_rows:
        cid, uname, cname = row[0], row[1], row[2]
        if uname:
            slug_to_id[uname.lower()] = cid
        if cname:
            norm = normalize_company_name(cname)
            if norm:
                name_to_id[norm.lower()] = cid

    click.echo(f"Target companies: {len(target_rows)} (slugs: {len(slug_to_id)}, names: {len(name_to_id)})")

    # --- Dry-run ---
    if dry_run:
        click.echo("Scanning PDL file for matches (dry run)...")
        matches = load_pdl_matches_indexed(str(pdl_path), slug_to_id, name_to_id)
        click.echo(f"Potential PDL matches: {len(matches)}")
        click.echo("Dry run — no DB writes performed.")
        return 0

    # --- Phase A: PDL enrichment (indexed lookup + batch commits) ---
    pdl_count = 0
    try:
        click.echo("Phase A: PDL enrichment (SQLite indexed lookup)...")
        matches = load_pdl_matches_indexed(str(pdl_path), slug_to_id, name_to_id)
        click.echo(f"PDL matches found: {len(matches)}")

        if matches:
            BATCH_SIZE = 500
            items = list(matches.items())
            for batch_start in range(0, len(items), BATCH_SIZE):
                batch = items[batch_start:batch_start + BATCH_SIZE]
                with db_manager.get_session(DbSessionType.WRITE) as session:
                    batch_count = 0
                    for company_id, fields in batch:
                        try:
                            if apply_pdl_enrichment(session, company_id, fields):
                                batch_count += 1
                        except Exception as e:
                            logger.warning("Skipping company %s: %s", company_id, e)
                    pdl_count += batch_count
                click.echo(f"  Batch {batch_start // BATCH_SIZE + 1}: {batch_count} enriched (total: {pdl_count})")

        click.echo(f"PDL-enriched: {pdl_count}")
    except Exception:
        logger.exception("PDL enrichment failed")
        click.echo(f"PDL enrichment failed (progress saved: {pdl_count} already committed).", err=True)
        return 1

    # --- Phase B: Wikidata gap-fill (separate transaction) ---
    wiki_count = 0
    if not skip_wikidata:
        try:
            click.echo("Phase B: Wikidata gap-fill...")
            with db_manager.get_session(DbSessionType.WRITE) as session:
                wiki_count = run_wikidata_gapfill(session, limit=wikidata_limit)
            click.echo(f"Wikidata-enriched: {wiki_count}")
        except Exception:
            logger.exception("Wikidata gap-fill failed")
            click.echo("Wikidata gap-fill failed (PDL data already committed).", err=True)

    # --- Summary ---
    total = len(target_rows)
    click.echo(f"\n=== Enrichment Summary ===")
    click.echo(f"Target companies: {total}")
    click.echo(f"PDL-enriched: {pdl_count} ({100 * pdl_count // total if total else 0}%)")
    click.echo(f"Wikidata-enriched: {wiki_count} ({100 * wiki_count // total if total else 0}%)")

    # Coverage stats
    with db_manager.get_session(DbSessionType.WRITE) as session:
        coverage = session.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(industry) AS has_industry,
                COUNT(website) AS has_website,
                COUNT(size_tier) AS has_size_tier
            FROM company
        """)).fetchone()
        if coverage:
            t = coverage[0] or 1
            click.echo(f"\nCoverage (all companies):")
            click.echo(f"  Industry: {coverage[1]}/{t} ({100 * coverage[1] // t}%)")
            click.echo(f"  Website:  {coverage[2]}/{t} ({100 * coverage[2] // t}%)")
            click.echo(f"  Size tier: {coverage[3]}/{t} ({100 * coverage[3] // t}%)")

    return 0


if __name__ == "__main__":
    main()

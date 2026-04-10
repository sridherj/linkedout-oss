# SPDX-License-Identifier: Apache-2.0
"""Smoke test: restore the real demo dump and run actual search queries.

Verifies that the demo dump contains valid embeddings and that vector
similarity search, affinity scores, and basic data integrity all work.

Requires:
    - PostgreSQL with pgvector extension
    - DATABASE_URL environment variable pointing to a Postgres cluster
    - demo-seed.dump file at DEMO_DUMP_PATH (or default location)
"""
from __future__ import annotations

import os
import subprocess
import sys
from urllib.parse import urlparse, urlunparse

import psycopg2
import psycopg2.extras
import pytest

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://linkedout_test:linkedout_test@localhost:5432/linkedout_test",
)
DEMO_DB = "linkedout_demo_smoke"
DEMO_DUMP_PATH = os.environ.get("DEMO_DUMP_PATH", "demo-seed.dump")

# Minimum thresholds for the demo dump
MIN_PROFILES = 2000
MIN_COMPANIES = 1000
MIN_CONNECTIONS = 2000
MIN_EMBEDDED = 2000
MIN_WITH_AFFINITY = 100


def _can_connect_to_demo_db() -> bool:
    """Check if the demo smoke database exists and is connectable."""
    try:
        parsed = urlparse(DB_URL)
        demo_url = urlunparse(parsed._replace(path=f"/{DEMO_DB}"))
        conn = psycopg2.connect(demo_url)
        conn.close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _can_connect_to_demo_db(),
    reason=f"Database '{DEMO_DB}' does not exist — run demo setup first",
)


def _replace_db(url: str, dbname: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{dbname}"))


def _maintenance_url() -> str:
    return _replace_db(DB_URL, "postgres")


def _demo_url() -> str:
    return _replace_db(DB_URL, DEMO_DB)


def _psql(url: str, sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["psql", url, "-c", sql],
        capture_output=True, text=True, timeout=30,
    )


def setup_demo_db():
    """Create demo DB, enable pgvector, restore dump."""
    maint = _maintenance_url()
    _psql(maint, f'DROP DATABASE IF EXISTS "{DEMO_DB}";')
    result = _psql(maint, f'CREATE DATABASE "{DEMO_DB}";')
    if result.returncode != 0:
        print(f"FAIL: Could not create database: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    demo = _demo_url()
    _psql(demo, "CREATE EXTENSION IF NOT EXISTS vector;")

    # Restore dump
    result = subprocess.run(
        ["pg_restore", f"--dbname={demo}", "--clean", "--if-exists", "--no-owner", DEMO_DUMP_PATH],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode not in (0, 1):
        print(f"FAIL: pg_restore failed (exit {result.returncode}): {result.stderr[:1000]}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: Demo database restored from {DEMO_DUMP_PATH}")


def teardown_demo_db():
    """Drop the smoke test database."""
    _psql(_maintenance_url(), f'DROP DATABASE IF EXISTS "{DEMO_DB}";')
    print("OK: Cleaned up smoke test database")


def get_conn():
    return psycopg2.connect(_demo_url())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_data_integrity():
    """Verify the dump has expected record counts."""
    conn = get_conn()
    cur = conn.cursor()

    checks = {
        "profiles": ("SELECT count(*) FROM crawled_profile", MIN_PROFILES),
        "companies": ("SELECT count(*) FROM company", MIN_COMPANIES),
        "connections": ("SELECT count(*) FROM connection", MIN_CONNECTIONS),
    }

    for label, (sql, minimum) in checks.items():
        cur.execute(sql)
        count = cur.fetchone()[0]
        if count < minimum:
            print(f"FAIL: {label} count {count} < minimum {minimum}")
            conn.close()
            return False
        print(f"  {label}: {count:,} (>= {minimum})")

    conn.close()
    return True


def test_embeddings_populated():
    """Verify profiles have nomic embeddings."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM crawled_profile WHERE embedding_nomic IS NOT NULL")
    embedded = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM crawled_profile")
    total = cur.fetchone()[0]

    coverage = embedded / total * 100 if total > 0 else 0
    print(f"  Embedded: {embedded:,}/{total:,} ({coverage:.0f}%)")

    if embedded < MIN_EMBEDDED:
        print(f"FAIL: Only {embedded} profiles embedded, need >= {MIN_EMBEDDED}")
        conn.close()
        return False

    # Check embedding dimensions
    cur.execute("""
        SELECT array_length(embedding_nomic::real[], 1)
        FROM crawled_profile
        WHERE embedding_nomic IS NOT NULL
        LIMIT 1
    """)
    dim = cur.fetchone()[0]
    if dim != 768:
        print(f"FAIL: Expected 768-dim embeddings, got {dim}")
        conn.close()
        return False
    print(f"  Dimensions: {dim}")

    conn.close()
    return True


def test_vector_search():
    """Run a cosine similarity search and verify results come back."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get a reference embedding from the first profile
    cur.execute("""
        SELECT id, full_name, embedding_nomic
        FROM crawled_profile
        WHERE embedding_nomic IS NOT NULL
        LIMIT 1
    """)
    ref = cur.fetchone()
    if not ref:
        print("FAIL: No profiles with embeddings found")
        conn.close()
        return False

    ref_embedding = ref["embedding_nomic"]

    # Run cosine similarity search (same pattern as vector_tool.py)
    cur.execute("""
        SELECT cp.id, cp.full_name, cp.headline,
               1 - (cp.embedding_nomic <=> %s::vector) AS similarity
        FROM crawled_profile cp
        WHERE cp.embedding_nomic IS NOT NULL
          AND cp.id != %s
        ORDER BY cp.embedding_nomic <=> %s::vector
        LIMIT 10
    """, (ref_embedding, ref["id"], ref_embedding))

    results = cur.fetchall()
    if len(results) < 5:
        print(f"FAIL: Vector search returned only {len(results)} results, expected >= 5")
        conn.close()
        return False

    print(f"  Query: similar to '{ref['full_name']}'")
    print(f"  Results: {len(results)} profiles")
    print(f"  Top similarity: {results[0]['similarity']:.4f}")
    print(f"  Bottom similarity: {results[-1]['similarity']:.4f}")

    # All similarities should be between 0 and 1
    for r in results:
        if not (0 <= r["similarity"] <= 1.001):
            print(f"FAIL: Invalid similarity {r['similarity']} for {r['full_name']}")
            conn.close()
            return False

    conn.close()
    return True


def test_semantic_search():
    """Run a text-based semantic search using an arbitrary profile's embedding as proxy.

    In CI we don't have the embedding model loaded, so we pick a 'distributed systems'
    engineer profile and search for similar ones — validating the search pipeline works.
    """
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Find a profile with 'engineer' or 'data' in headline to use as query seed
    cur.execute("""
        SELECT id, full_name, headline, embedding_nomic
        FROM crawled_profile
        WHERE embedding_nomic IS NOT NULL
          AND (headline ILIKE '%%engineer%%' OR headline ILIKE '%%data%%')
        LIMIT 1
    """)
    seed = cur.fetchone()
    if not seed:
        print("WARN: No engineer/data profiles found, using first profile")
        cur.execute("""
            SELECT id, full_name, headline, embedding_nomic
            FROM crawled_profile WHERE embedding_nomic IS NOT NULL LIMIT 1
        """)
        seed = cur.fetchone()

    # Search for similar profiles with minimum threshold (matching vector_tool.py)
    cur.execute("""
        SELECT cp.id, cp.full_name, cp.headline,
               1 - (cp.embedding_nomic <=> %s::vector) AS similarity
        FROM crawled_profile cp
        WHERE cp.embedding_nomic IS NOT NULL
          AND cp.id != %s
          AND 1 - (cp.embedding_nomic <=> %s::vector) > 0.25
        ORDER BY cp.embedding_nomic <=> %s::vector
        LIMIT 10
    """, (seed["embedding_nomic"], seed["id"], seed["embedding_nomic"], seed["embedding_nomic"]))

    results = cur.fetchall()
    print(f"  Seed: '{seed['full_name']}' - {seed['headline']}")
    print(f"  Results above 0.25 threshold: {len(results)}")

    if len(results) < 3:
        print(f"FAIL: Expected >= 3 results above threshold, got {len(results)}")
        conn.close()
        return False

    for r in results[:3]:
        print(f"    {r['similarity']:.3f}  {r['full_name']} - {r['headline']}")

    conn.close()
    return True


def test_affinity_scores():
    """Verify affinity scores are populated in connection records."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM connection WHERE affinity_score IS NOT NULL AND affinity_score > 0")
    with_affinity = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM connection")
    total = cur.fetchone()[0]

    coverage = with_affinity / total * 100 if total > 0 else 0
    print(f"  Connections with affinity: {with_affinity:,}/{total:,} ({coverage:.0f}%)")

    if with_affinity < MIN_WITH_AFFINITY:
        print(f"FAIL: Only {with_affinity} connections have affinity, need >= {MIN_WITH_AFFINITY}")
        conn.close()
        return False

    # Check score distribution makes sense
    cur.execute("""
        SELECT min(affinity_score), avg(affinity_score), max(affinity_score)
        FROM connection WHERE affinity_score > 0
    """)
    min_s, avg_s, max_s = cur.fetchone()
    print(f"  Score range: {min_s:.2f} - {max_s:.2f} (avg {avg_s:.2f})")

    if max_s <= min_s:
        print("FAIL: All affinity scores are identical — scoring likely broken")
        conn.close()
        return False

    conn.close()
    return True


def test_search_with_affinity_join():
    """Run the full search pattern: vector search joined with affinity (matching vector_tool.py)."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get a profile to search with
    cur.execute("""
        SELECT cp.id, cp.embedding_nomic
        FROM crawled_profile cp
        JOIN connection c ON c.crawled_profile_id = cp.id
        WHERE cp.embedding_nomic IS NOT NULL
          AND c.affinity_score IS NOT NULL
        LIMIT 1
    """)
    ref = cur.fetchone()
    if not ref:
        print("WARN: No profiles with both embedding and affinity — skipping")
        conn.close()
        return True

    # Full query matching vector_tool.py pattern
    cur.execute("""
        SELECT cp.id, cp.full_name, cp.headline,
               cp.current_position, cp.current_company_name,
               c.affinity_score, c.dunbar_tier,
               1 - (cp.embedding_nomic <=> %s::vector) AS similarity
        FROM crawled_profile cp
        JOIN connection c ON c.crawled_profile_id = cp.id
        WHERE cp.embedding_nomic IS NOT NULL
          AND 1 - (cp.embedding_nomic <=> %s::vector) > 0.25
        ORDER BY cp.embedding_nomic <=> %s::vector
        LIMIT 5
    """, (ref["embedding_nomic"], ref["embedding_nomic"], ref["embedding_nomic"]))

    results = cur.fetchall()
    print(f"  Full search+affinity results: {len(results)}")

    for r in results[:3]:
        affinity = r["affinity_score"] or 0
        print(f"    sim={r['similarity']:.3f} aff={affinity:.2f}  {r['full_name']} - {r['headline']}")

    if len(results) == 0:
        print("FAIL: Full search query returned no results")
        conn.close()
        return False

    conn.close()
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Demo Search Smoke Test")
    print("=" * 60)

    if not os.path.exists(DEMO_DUMP_PATH):
        print(f"SKIP: Demo dump not found at {DEMO_DUMP_PATH}")
        print(f"Set DEMO_DUMP_PATH to the path of demo-seed.dump")
        sys.exit(0)

    print(f"\nDump: {DEMO_DUMP_PATH}")
    print(f"DB:   {_demo_url()}\n")

    setup_demo_db()

    tests = [
        ("Data Integrity", test_data_integrity),
        ("Embeddings Populated", test_embeddings_populated),
        ("Vector Search", test_vector_search),
        ("Semantic Search (threshold)", test_semantic_search),
        ("Affinity Scores", test_affinity_scores),
        ("Search + Affinity Join", test_search_with_affinity_join),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n--- {name} ---")
        try:
            if test_fn():
                print(f"PASS: {name}")
                passed += 1
            else:
                print(f"FAIL: {name}")
                failed += 1
        except Exception as e:
            print(f"ERROR: {name}: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")

    teardown_demo_db()

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()

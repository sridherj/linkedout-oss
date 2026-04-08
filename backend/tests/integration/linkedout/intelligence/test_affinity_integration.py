# SPDX-License-Identifier: Apache-2.0
"""Integration tests for affinity scoring against PostgreSQL."""
import numpy as np
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.intelligence.scoring.affinity_scorer import (
    AFFINITY_VERSION,
    AffinityScorer,
)

pytestmark = pytest.mark.integration


class TestAffinityBatchComputation:
    """Test batch affinity computation end-to-end on PostgreSQL."""

    def test_all_connections_get_scores_and_tiers(
        self, integration_db_session: Session, intelligence_test_data
    ):
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        count = scorer.compute_for_user(user_a.id, reference_date=ref)

        assert count == 20  # User A has 20 connections

        # Verify all connections have scores and tiers
        for conn in intelligence_test_data['connections_a']:
            integration_db_session.refresh(conn)
            assert conn.affinity_score is not None
            assert conn.affinity_score >= 0
            assert conn.affinity_score <= 100
            assert conn.dunbar_tier in (
                'inner_circle', 'active', 'familiar', 'acquaintance'
            )
            assert conn.affinity_version == AFFINITY_VERSION
            assert conn.affinity_computed_at is not None


class TestDunbarTierDistribution:
    """Verify Dunbar tier assignment by rank."""

    def test_tier_boundaries(
        self, integration_db_session: Session, intelligence_test_data
    ):
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        # Refresh and sort by score descending
        conns = []
        for c in intelligence_test_data['connections_a']:
            integration_db_session.refresh(c)
            conns.append(c)
        # Use same tiebreaker as scorer so positions match ranks exactly
        conns.sort(key=lambda c: (-(c.affinity_score or 0), c.id))

        # With 20 connections: top 15 = inner_circle, 16-20 = active
        tiers = [c.dunbar_tier for c in conns]
        assert all(t == 'inner_circle' for t in tiers[:15])
        assert all(t == 'active' for t in tiers[15:20])


class TestAffinitySignalsStored:
    """Verify individual signal columns are populated."""

    def test_signal_columns_populated(
        self, integration_db_session: Session, intelligence_test_data
    ):
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        for conn in intelligence_test_data['connections_a']:
            integration_db_session.refresh(conn)
            # Source count signal should be >= 0
            assert conn.affinity_source_count >= 0
            # Recency should be set (all have connected_at)
            assert conn.affinity_recency >= 0
            # Career overlap can be 0 but should be set
            assert conn.affinity_career_overlap >= 0
            # Mutual connections is 0
            assert conn.affinity_mutual_connections == 0.0
            # External contact can be 0 but should be set
            assert conn.affinity_external_contact >= 0
            # Embedding similarity can be 0 but should be set
            assert conn.affinity_embedding_similarity >= 0

    def test_career_overlap_nonzero_for_shared_companies(
        self, integration_db_session: Session, intelligence_test_data
    ):
        """Connection with shared company experience should have nonzero career overlap."""
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        # connections_a[1] has profile that worked at Google
        # and user A's own profile (profiles_a[0]) also worked at Google
        conn_with_overlap = intelligence_test_data['connections_a'][1]
        integration_db_session.refresh(conn_with_overlap)
        assert conn_with_overlap.affinity_career_overlap > 0


class TestAffinityIdempotent:
    """Running affinity computation twice produces same results."""

    def test_recompute_idempotent(
        self, integration_db_session: Session, intelligence_test_data
    ):
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)

        # First computation
        scorer.compute_for_user(user_a.id, reference_date=ref)
        first_scores = {}
        for c in intelligence_test_data['connections_a']:
            integration_db_session.refresh(c)
            first_scores[c.id] = (c.affinity_score, c.dunbar_tier)

        # Second computation
        scorer.compute_for_user(user_a.id, reference_date=ref)
        for c in intelligence_test_data['connections_a']:
            integration_db_session.refresh(c)
            assert c.affinity_score == first_scores[c.id][0]
            assert c.dunbar_tier == first_scores[c.id][1]


class TestExternalContactSignal:
    """Verify external contact signal from contact_source table."""

    def test_phone_contact_scores_one(
        self, integration_db_session: Session, intelligence_test_data
    ):
        """Connection with phone in contact_source should get external_contact = 1.0."""
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        # connections_a[0] has phone contact (contacts_phone source type)
        conn = intelligence_test_data['connections_a'][0]
        integration_db_session.refresh(conn)
        assert conn.affinity_external_contact == 1.0

    def test_email_only_contact_scores_point_seven(
        self, integration_db_session: Session, intelligence_test_data
    ):
        """Connection with email-only contact should get external_contact = 0.7."""
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        # connections_a[1] has email-only contact (gmail_email_only)
        conn = intelligence_test_data['connections_a'][1]
        integration_db_session.refresh(conn)
        assert conn.affinity_external_contact == 0.7

    def test_google_work_contact_scores_point_seven(
        self, integration_db_session: Session, intelligence_test_data
    ):
        """Google work contact (email-only) should get external_contact = 0.7."""
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        # connections_a[2] has google_contacts_job source type
        conn = intelligence_test_data['connections_a'][2]
        integration_db_session.refresh(conn)
        assert conn.affinity_external_contact == 0.7

    def test_no_contact_source_scores_zero(
        self, integration_db_session: Session, intelligence_test_data
    ):
        """Connection without contact_source rows should get external_contact = 0.0."""
        user_a = intelligence_test_data['user_a']
        ref = date(2026, 3, 28)

        scorer = AffinityScorer(integration_db_session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        # connections_a[5] has no contact_source rows
        conn = intelligence_test_data['connections_a'][5]
        integration_db_session.refresh(conn)
        assert conn.affinity_external_contact == 0.0


class TestEmbeddingSimilaritySignal:
    """Verify embedding similarity signal using pgvector cosine distance."""

    def test_embedding_similarity_nonzero_when_both_have_embeddings(
        self, integration_db_session: Session, intelligence_test_data, vector_column_ready
    ):
        """When user and connection both have embeddings, similarity should be > 0."""
        if not vector_column_ready:
            pytest.skip('pgvector not available')

        session = integration_db_session
        user_a = intelligence_test_data['user_a']
        profiles_a = intelligence_test_data['profiles_a']

        # Create a deterministic 1536-dim embedding for user's own profile
        rng = np.random.default_rng(42)
        user_vec = rng.standard_normal(1536).astype(np.float32)
        user_emb_str = '[' + ','.join(str(float(v)) for v in user_vec) + ']'
        session.execute(text(
            "UPDATE crawled_profile SET embedding = CAST(:emb AS vector) WHERE id = :pid"
        ), {'emb': user_emb_str, 'pid': profiles_a[0].id})

        # Create a similar embedding for connections_a[1] (add small noise)
        conn_vec = user_vec + rng.standard_normal(1536).astype(np.float32) * 0.1
        conn_emb_str = '[' + ','.join(str(float(v)) for v in conn_vec) + ']'
        session.execute(text(
            "UPDATE crawled_profile SET embedding = CAST(:emb AS vector) WHERE id = :pid"
        ), {'emb': conn_emb_str, 'pid': profiles_a[1].id})

        session.flush()
        session.expire_all()  # Force ORM to re-fetch after raw SQL updates

        ref = date(2026, 3, 28)
        scorer = AffinityScorer(session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        conn = intelligence_test_data['connections_a'][1]
        session.refresh(conn)
        assert conn.affinity_embedding_similarity > 0.0
        # Similar vectors should have high similarity (>0.5)
        assert conn.affinity_embedding_similarity > 0.5

    def test_embedding_similarity_zero_when_connection_has_no_embedding(
        self, integration_db_session: Session, intelligence_test_data, vector_column_ready
    ):
        """When connection has no embedding, similarity should be 0.0."""
        if not vector_column_ready:
            pytest.skip('pgvector not available')

        session = integration_db_session
        user_a = intelligence_test_data['user_a']

        ref = date(2026, 3, 28)
        scorer = AffinityScorer(session)
        scorer.compute_for_user(user_a.id, reference_date=ref)

        # connections_a[10] has no embedding (profiles_a[10] has no embedding set)
        conn = intelligence_test_data['connections_a'][10]
        session.refresh(conn)
        assert conn.affinity_embedding_similarity == 0.0

    def test_embedding_vector_format_roundtrip(
        self, integration_db_session: Session, intelligence_test_data, vector_column_ready
    ):
        """Verify embedding stored as pgvector can be read back and used for cosine distance."""
        if not vector_column_ready:
            pytest.skip('pgvector not available')

        session = integration_db_session
        profiles_a = intelligence_test_data['profiles_a']

        # Write a known vector
        known_vec = [0.1] * 1536
        emb_str = '[' + ','.join(str(v) for v in known_vec) + ']'
        session.execute(text(
            "UPDATE crawled_profile SET embedding = CAST(:emb AS vector) WHERE id = :pid"
        ), {'emb': emb_str, 'pid': profiles_a[3].id})
        session.flush()

        # Read it back and verify cosine distance with itself is 0 (similarity = 1)
        row = session.execute(text(
            "SELECT 1 - (embedding <=> CAST(:emb AS vector)) AS sim "
            "FROM crawled_profile WHERE id = :pid"
        ), {'emb': emb_str, 'pid': profiles_a[3].id}).fetchone()

        assert row is not None
        assert abs(row[0] - 1.0) < 0.001  # Self-similarity should be ~1.0

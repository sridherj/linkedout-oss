# SPDX-License-Identifier: Apache-2.0
"""Integration tests for PostgreSQL RLS tenant isolation.

These tests verify that Row-Level Security policies correctly enforce
per-user data isolation via ``get_session(app_user_id=...)``.

Test categories:
1. Cross-user isolation — two app_users see only their own connections/profiles
2. Fail-closed — unset session variable returns 0 rows (not all rows)
3. Reference data — company/company_alias are NOT RLS-protected
4. Complex queries — RLS works across JOINs, CTEs, and direct table access

See also: migration d1e2f3a4b5c6_enable_rls_policies.py for the production
RLS policies these tests mirror.
"""

import pytest
from sqlalchemy import text

from shared.infra.db.db_session_manager import db_session_manager

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("rls_policies_applied"),
]


class TestRLSCrossUserIsolation:
    """Verify that two different users see only their own data."""

    def test_user_a_sees_own_connections(
        self, intelligence_test_data
    ):
        user_a = intelligence_test_data['user_a']
        with db_session_manager.get_session(app_user_id=user_a.id) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM connection")
            ).scalar()
            # User A has 20 connections in test data
            assert result == 20

    def test_user_b_sees_own_connections(
        self, intelligence_test_data
    ):
        user_b = intelligence_test_data['user_b']
        with db_session_manager.get_session(app_user_id=user_b.id) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM connection")
            ).scalar()
            # User B has 5 connections in test data
            assert result == 5

    def test_user_a_cannot_see_user_b_profiles(
        self, intelligence_test_data
    ):
        user_a = intelligence_test_data['user_a']
        with db_session_manager.get_session(app_user_id=user_a.id) as session:
            result = session.execute(
                text(
                    "SELECT COUNT(*) FROM crawled_profile cp "
                    "WHERE cp.full_name LIKE 'PersonB%'"
                )
            ).scalar()
            assert result == 0

    def test_user_b_cannot_see_user_a_profiles(
        self, intelligence_test_data
    ):
        user_b = intelligence_test_data['user_b']
        with db_session_manager.get_session(app_user_id=user_b.id) as session:
            result = session.execute(
                text(
                    "SELECT COUNT(*) FROM crawled_profile cp "
                    "WHERE cp.full_name LIKE 'PersonA%'"
                )
            ).scalar()
            assert result == 0


class TestRLSFailClosed:
    """Verify fail-closed behavior when session variable is not set."""

    def test_no_session_var_returns_zero_rows(self):
        """Without set_config, the session variable defaults to empty string.
        NULLIF converts '' to NULL, and uuid cast of NULL returns NULL,
        so no rows match."""
        # Use the search engine directly without setting the session variable
        factory = db_session_manager._SessionLocal
        if not factory:
            pytest.skip("No session factory available")

        session = factory()
        try:
            result = session.execute(
                text("SELECT COUNT(*) FROM connection")
            ).scalar()
            assert result == 0, f"Expected 0 rows without session var, got {result}"

            result = session.execute(
                text("SELECT COUNT(*) FROM crawled_profile")
            ).scalar()
            assert result == 0, f"Expected 0 crawled_profiles without session var, got {result}"
        finally:
            session.rollback()
            session.close()


class TestRLSReferenceDataAccessible:
    """Verify company and company_alias are NOT RLS-protected."""

    def test_company_accessible_without_user_context(self):
        """company table should be readable regardless of session variable."""
        factory = db_session_manager._SessionLocal
        if not factory:
            pytest.skip("No session factory available")

        session = factory()
        try:
            result = session.execute(
                text("SELECT COUNT(*) FROM company")
            ).scalar()
            # Should return all companies (not filtered by any user)
            assert result > 0, "company table should have data accessible to all"
        finally:
            session.rollback()
            session.close()

    def test_company_alias_accessible_without_user_context(self):
        """company_alias table should be readable regardless of session variable."""
        factory = db_session_manager._SessionLocal
        if not factory:
            pytest.skip("No session factory available")

        session = factory()
        try:
            # company_alias may or may not have data, but the query should not error
            result = session.execute(
                text("SELECT COUNT(*) FROM company_alias")
            ).scalar()
            assert result >= 0
        finally:
            session.rollback()
            session.close()


class TestRLSAcrossQueryPatterns:
    """Verify RLS works correctly across complex query patterns."""

    def test_join_through_experience(
        self, intelligence_test_data
    ):
        """Experience data is scoped to user's connected profiles."""
        user_a = intelligence_test_data['user_a']
        with db_session_manager.get_session(app_user_id=user_a.id) as session:
            result = session.execute(
                text(
                    "SELECT COUNT(*) FROM experience e "
                    "JOIN crawled_profile cp ON cp.id = e.crawled_profile_id"
                )
            ).scalar()
            assert result > 0, "User A should see experiences for their connected profiles"

    def test_cte_respects_rls(
        self, intelligence_test_data
    ):
        """CTE queries are filtered by RLS."""
        user_a = intelligence_test_data['user_a']
        with db_session_manager.get_session(app_user_id=user_a.id) as session:
            result = session.execute(
                text(
                    "WITH profile_count AS ("
                    "  SELECT COUNT(*) AS cnt FROM crawled_profile"
                    ") SELECT cnt FROM profile_count"
                )
            ).scalar()
            # Should only count user A's connected profiles
            assert result == 20

    def test_direct_profile_access_scoped(
        self, intelligence_test_data
    ):
        """Direct crawled_profile query without JOIN is still scoped by RLS."""
        user_a = intelligence_test_data['user_a']
        with db_session_manager.get_session(app_user_id=user_a.id) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM crawled_profile")
            ).scalar()
            assert result == 20, "Direct profile access should be RLS-scoped"

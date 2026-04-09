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

import contextlib
import os

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("rls_policies_applied"),
]

_RLS_APP_ROLE = 'linkedout_app_role'
_SESSION_VAR = 'app.current_user_id'
_worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'gw0')
_TEST_SCHEMA = f'integration_test_{_worker_id}'


@contextlib.contextmanager
def _rls_session(engine, app_user_id=None):
    """Open a session as the non-superuser app role so RLS is enforced."""
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        session.execute(text(f"SET ROLE {_RLS_APP_ROLE}"))
        session.execute(text(f"SET search_path TO {_TEST_SCHEMA}, public"))
        if app_user_id:
            session.execute(
                text(f"SELECT set_config('{_SESSION_VAR}', :uid, TRUE)"),
                {'uid': str(app_user_id)},
            )
        yield session
    finally:
        session.execute(text("RESET ROLE"))
        session.rollback()
        session.close()


class TestRLSCrossUserIsolation:
    """Verify that two different users see only their own data."""

    def test_user_a_sees_own_connections(
        self, intelligence_test_data, integration_db_engine
    ):
        user_a = intelligence_test_data['user_a']
        with _rls_session(integration_db_engine, app_user_id=user_a.id) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM connection")
            ).scalar()
            # User A has 20 connections in test data
            assert result == 20

    def test_user_b_sees_own_connections(
        self, intelligence_test_data, integration_db_engine
    ):
        user_b = intelligence_test_data['user_b']
        with _rls_session(integration_db_engine, app_user_id=user_b.id) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM connection")
            ).scalar()
            # User B has 5 connections in test data
            assert result == 5

    def test_user_a_cannot_see_user_b_profiles(
        self, intelligence_test_data, integration_db_engine
    ):
        user_a = intelligence_test_data['user_a']
        with _rls_session(integration_db_engine, app_user_id=user_a.id) as session:
            result = session.execute(
                text(
                    "SELECT COUNT(*) FROM crawled_profile cp "
                    "WHERE cp.full_name LIKE 'PersonB%'"
                )
            ).scalar()
            assert result == 0

    def test_user_b_cannot_see_user_a_profiles(
        self, intelligence_test_data, integration_db_engine
    ):
        user_b = intelligence_test_data['user_b']
        with _rls_session(integration_db_engine, app_user_id=user_b.id) as session:
            result = session.execute(
                text(
                    "SELECT COUNT(*) FROM crawled_profile cp "
                    "WHERE cp.full_name LIKE 'PersonA%'"
                )
            ).scalar()
            assert result == 0


class TestRLSFailClosed:
    """Verify fail-closed behavior when session variable is not set."""

    def test_no_session_var_returns_zero_rows(self, integration_db_engine):
        """Without set_config, the session variable defaults to empty string.
        NULLIF converts '' to NULL, and uuid cast of NULL returns NULL,
        so no rows match."""
        with _rls_session(integration_db_engine) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM connection")
            ).scalar()
            assert result == 0, f"Expected 0 rows without session var, got {result}"

            result = session.execute(
                text("SELECT COUNT(*) FROM crawled_profile")
            ).scalar()
            assert result == 0, f"Expected 0 crawled_profiles without session var, got {result}"


class TestRLSReferenceDataAccessible:
    """Verify company and company_alias are NOT RLS-protected."""

    def test_company_accessible_without_user_context(self, integration_db_engine):
        """company table should be readable regardless of session variable."""
        with _rls_session(integration_db_engine) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM company")
            ).scalar()
            # Should return all companies (not filtered by any user)
            assert result > 0, "company table should have data accessible to all"

    def test_company_alias_accessible_without_user_context(self, integration_db_engine):
        """company_alias table should be readable regardless of session variable."""
        with _rls_session(integration_db_engine) as session:
            # company_alias may or may not have data, but the query should not error
            result = session.execute(
                text("SELECT COUNT(*) FROM company_alias")
            ).scalar()
            assert result >= 0


class TestRLSAcrossQueryPatterns:
    """Verify RLS works correctly across complex query patterns."""

    def test_join_through_experience(
        self, intelligence_test_data, integration_db_engine
    ):
        """Experience data is scoped to user's connected profiles."""
        user_a = intelligence_test_data['user_a']
        with _rls_session(integration_db_engine, app_user_id=user_a.id) as session:
            result = session.execute(
                text(
                    "SELECT COUNT(*) FROM experience e "
                    "JOIN crawled_profile cp ON cp.id = e.crawled_profile_id"
                )
            ).scalar()
            assert result > 0, "User A should see experiences for their connected profiles"

    def test_cte_respects_rls(
        self, intelligence_test_data, integration_db_engine
    ):
        """CTE queries are filtered by RLS."""
        user_a = intelligence_test_data['user_a']
        with _rls_session(integration_db_engine, app_user_id=user_a.id) as session:
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
        self, intelligence_test_data, integration_db_engine
    ):
        """Direct crawled_profile query without JOIN is still scoped by RLS."""
        user_a = intelligence_test_data['user_a']
        with _rls_session(integration_db_engine, app_user_id=user_a.id) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM crawled_profile")
            ).scalar()
            assert result == 20, "Direct profile access should be RLS-scoped"

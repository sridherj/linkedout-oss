# SPDX-License-Identifier: Apache-2.0
"""Fixtures for intelligence integration tests.

Creates test data with two users, connections, profiles, and experiences
for testing user isolation, SQL tool, affinity scoring, and vector search.
"""
import os

import pytest
from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session

_worker_id = os.environ.get('PYTEST_XDIST_WORKER', 'gw0')
_TEST_SCHEMA = f'integration_test_{_worker_id}'

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.contact_source.entities.contact_source_entity import ContactSourceEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from linkedout.experience.entities.experience_entity import ExperienceEntity
from linkedout.company.entities.company_entity import CompanyEntity
from linkedout.import_job.entities.import_job_entity import ImportJobEntity
from organization.entities.app_user_entity import AppUserEntity


@pytest.fixture(scope='session')
def pgvector_available(integration_db_engine):
    """Check if pgvector extension is available."""
    try:
        with integration_db_engine.connect() as conn:
            # Extension lives in public schema; make sure it's accessible
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public"))
            conn.commit()
        return True
    except Exception:
        return False


@pytest.fixture(scope='session')
def vector_column_ready(integration_db_engine, integration_db_session, pgvector_available, intelligence_test_data):
    """Alter embedding column to vector type if pgvector is available.

    Depends on intelligence_test_data to ensure tables are seeded before ALTER.
    Also sets search_path on the session to include public for vector type visibility.
    """
    if not pgvector_available:
        return False
    try:
        # Use the same session so the ALTER TABLE doesn't deadlock with ACCESS SHARE
        # locks held by prior tests in the same session transaction.  Within one
        # transaction PostgreSQL always grants your own lock-upgrade requests.
        integration_db_session.execute(text(f"SET search_path TO {_TEST_SCHEMA}, public"))
        integration_db_session.execute(text(
            "ALTER TABLE crawled_profile "
            "ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector(1536)"
        ))
        integration_db_session.commit()
        return True
    except Exception:
        return False


@pytest.fixture(scope='session')
def intelligence_test_data(integration_db_session: Session, seeded_data):
    """Create intelligence-specific test data: 2 users with separate connections.

    Returns dict with keys: user_a, user_b, profiles_a, profiles_b,
    connections_a, connections_b, companies.
    """
    session = integration_db_session

    # Get existing tenant/BU from seeded data
    tenant = seeded_data['tenant'][0]
    bu = seeded_data['bu'][0]

    # Create two app users for isolation testing
    user_a = AppUserEntity(
        email='intel_user_a@test.com',
        name='Intel User A',
        auth_provider_id='auth0|intel_a',
    )
    user_b = AppUserEntity(
        email='intel_user_b@test.com',
        name='Intel User B',
        auth_provider_id='auth0|intel_b',
    )
    session.add_all([user_a, user_b])
    session.flush()

    # Create companies for career overlap testing
    company_google = CompanyEntity(
        canonical_name='Google',
        normalized_name='google',
        domain='google.com',
        industry='Technology',
        size_tier='large',
        estimated_employee_count=150000,
        network_connection_count=0,
    )
    company_stripe = CompanyEntity(
        canonical_name='Stripe',
        normalized_name='stripe',
        domain='stripe.com',
        industry='Fintech',
        size_tier='large',
        estimated_employee_count=8000,
        network_connection_count=0,
    )
    company_acme = CompanyEntity(
        canonical_name='Acme Corp',
        normalized_name='acme corp',
        domain='acme.com',
        industry='Technology',
        size_tier='mid',
        estimated_employee_count=50,
        network_connection_count=0,
    )
    session.add_all([company_google, company_stripe, company_acme])
    session.flush()

    # Create profiles for User A (mix of enriched and stub)
    profiles_a = []
    for i in range(20):
        enriched = i < 15  # 15 enriched, 5 stubs
        p = CrawledProfileEntity(
            linkedin_url=f'https://www.linkedin.com/in/intel-a-{i}',
            public_identifier=f'intel-a-{i}',
            first_name=f'PersonA{i}',
            last_name='Test',
            full_name=f'PersonA{i} Test',
            headline=f'Engineer at Company {i}',
            current_company_name='Google' if i < 5 else 'Stripe' if i < 10 else 'Acme Corp',
            current_position='Software Engineer' if i < 10 else 'Product Manager',
            location_city='San Francisco' if i < 10 else 'New York',
            location_country='US',
            data_source='test',
            has_enriched_data=enriched,
            source_app_user_id=user_a.id if i == 0 else None,
        )
        profiles_a.append(p)
    session.add_all(profiles_a)
    session.flush()

    # Link user A's own profile for career overlap computation
    user_a.own_crawled_profile_id = profiles_a[0].id
    session.flush()

    # Create connections for User A
    connections_a = []
    for i, p in enumerate(profiles_a):
        src_count = 3 if i < 5 else 2 if i < 10 else 1
        c = ConnectionEntity(
            tenant_id=tenant.id,
            bu_id=bu.id,
            app_user_id=user_a.id,
            crawled_profile_id=p.id,
            connected_at=date(2025, 6, 1) if i < 10 else date(2022, 1, 1),
            sources=['linkedin', 'gmail', 'google_contacts'][:src_count],
        )
        connections_a.append(c)
    session.add_all(connections_a)
    session.flush()

    # Create profiles for User B (smaller set)
    profiles_b = []
    for i in range(5):
        p = CrawledProfileEntity(
            linkedin_url=f'https://www.linkedin.com/in/intel-b-{i}',
            public_identifier=f'intel-b-{i}',
            first_name=f'PersonB{i}',
            last_name='Other',
            full_name=f'PersonB{i} Other',
            headline=f'Designer {i}',
            current_company_name='DesignCo',
            current_position='Designer',
            location_city='London',
            location_country='UK',
            data_source='test',
            has_enriched_data=True,
        )
        profiles_b.append(p)
    session.add_all(profiles_b)
    session.flush()

    connections_b = []
    for p in profiles_b:
        c = ConnectionEntity(
            tenant_id=tenant.id,
            bu_id=bu.id,
            app_user_id=user_b.id,
            crawled_profile_id=p.id,
            connected_at=date(2025, 1, 1),
            sources=['linkedin'],
        )
        connections_b.append(c)
    session.add_all(connections_b)
    session.flush()

    # Create experiences for career overlap / warm intro tests
    # User A's own profile (profiles_a[0]) worked at Google
    session.add(ExperienceEntity(
        crawled_profile_id=profiles_a[0].id,
        position='Software Engineer',
        company_name='Google',
        company_id=company_google.id,
        start_date=date(2018, 1, 1),
        end_date=None,
        is_current=True,
    ))

    # profiles_a[1] also worked at Google (warm intro candidate)
    session.add(ExperienceEntity(
        crawled_profile_id=profiles_a[1].id,
        position='Senior Engineer',
        company_name='Google',
        company_id=company_google.id,
        start_date=date(2019, 6, 1),
        end_date=date(2023, 6, 1),
        is_current=False,
    ))

    # profiles_a[2] worked at Stripe (different company)
    session.add(ExperienceEntity(
        crawled_profile_id=profiles_a[2].id,
        position='Backend Engineer',
        company_name='Stripe',
        company_id=company_stripe.id,
        start_date=date(2020, 1, 1),
        end_date=None,
        is_current=True,
    ))

    # profiles_a[5] also worked at Google AND Stripe (strong overlap)
    session.add_all([
        ExperienceEntity(
            crawled_profile_id=profiles_a[5].id,
            position='Engineer',
            company_name='Google',
            company_id=company_google.id,
            start_date=date(2017, 1, 1),
            end_date=date(2021, 1, 1),
            is_current=False,
        ),
        ExperienceEntity(
            crawled_profile_id=profiles_a[5].id,
            position='Engineer',
            company_name='Stripe',
            company_id=company_stripe.id,
            start_date=date(2021, 1, 1),
            end_date=None,
            is_current=True,
        ),
    ])

    # Create an import job for contact_source FK
    import_job = ImportJobEntity(
        app_user_id=user_a.id,
        tenant_id=tenant.id,
        bu_id=bu.id,
        source_type='gmail_contacts',
        status='complete',
        total_records=3,
    )
    session.add(import_job)
    session.flush()

    # Create contact_source rows for external contact signal testing
    # connections_a[0] has a phone contact (score 1.0)
    session.add(ContactSourceEntity(
        app_user_id=user_a.id,
        tenant_id=tenant.id,
        bu_id=bu.id,
        import_job_id=import_job.id,
        source_type='contacts_phone',
        source_label='google_personal',
        full_name=profiles_a[0].full_name,
        phone='+14155551234',
        email='persona0@test.com',
        connection_id=connections_a[0].id,
        dedup_status='matched',
        dedup_method='email',
    ))
    # connections_a[1] has email-only contact (score 0.7)
    session.add(ContactSourceEntity(
        app_user_id=user_a.id,
        tenant_id=tenant.id,
        bu_id=bu.id,
        import_job_id=import_job.id,
        source_type='gmail_email_only',
        source_label='google_personal',
        full_name=profiles_a[1].full_name,
        email='persona1@test.com',
        connection_id=connections_a[1].id,
        dedup_status='matched',
        dedup_method='email',
    ))
    # connections_a[2] has google work contact (score 0.7)
    session.add(ContactSourceEntity(
        app_user_id=user_a.id,
        tenant_id=tenant.id,
        bu_id=bu.id,
        import_job_id=import_job.id,
        source_type='google_contacts_job',
        source_label='google_work',
        full_name=profiles_a[2].full_name,
        email='persona2@google.com',
        connection_id=connections_a[2].id,
        dedup_status='matched',
        dedup_method='email',
    ))

    session.flush()
    session.commit()

    return {
        'user_a': user_a,
        'user_b': user_b,
        'tenant': tenant,
        'bu': bu,
        'profiles_a': profiles_a,
        'profiles_b': profiles_b,
        'connections_a': connections_a,
        'connections_b': connections_b,
        'companies': {
            'google': company_google,
            'stripe': company_stripe,
            'acme': company_acme,
        },
        'import_job': import_job,
    }


# ---------------------------------------------------------------------------
# RLS test fixtures
#
# This fixture enables the RLS isolation tests in test_rls_isolation.py.
# It is MODULE-scoped (not session-scoped) for an important reason:
#
#   FORCE ROW LEVEL SECURITY makes even the table owner subject to RLS.
#   If it were session-scoped, every subsequent test module that queries
#   RLS-protected tables without app_user_id would see 0 rows.
#   Module scope ensures policies are applied only while
#   test_rls_isolation.py runs, then torn down before other modules execute.
#
# The DDL runs on integration_db_session (not a new connection) to avoid
# AccessExclusive lock contention.
#
# See also: migration d1e2f3a4b5c6_enable_rls_policies.py
# ---------------------------------------------------------------------------


_RLS_APP_ROLE = 'linkedout_app_role'


@pytest.fixture(scope='module')
def rls_policies_applied(integration_db_session, integration_db_engine, intelligence_test_data):
    """Apply RLS policies to the test schema, mirroring migration d1e2f3a4b5c6.

    Also creates a non-superuser role so RLS policies are actually enforced.
    PostgreSQL superusers bypass RLS even with FORCE ROW LEVEL SECURITY.
    """
    _SESSION_VAR = "app.current_user_id"
    _PROFILE_TABLES = ['crawled_profile', 'experience', 'education', 'profile_skill']

    session = integration_db_session

    # Create a non-superuser role for RLS testing.
    # Superusers bypass RLS even with FORCE, so we need a regular role.
    session.execute(text(
        f"DO $$ BEGIN "
        f"  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_RLS_APP_ROLE}') THEN "
        f"    CREATE ROLE {_RLS_APP_ROLE} NOLOGIN; "
        f"  END IF; "
        f"END $$"
    ))
    session.execute(text(f"GRANT USAGE ON SCHEMA {_TEST_SCHEMA} TO {_RLS_APP_ROLE}"))
    session.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {_TEST_SCHEMA} TO {_RLS_APP_ROLE}"))

    # Composite index for policy subquery performance
    session.execute(text(
        f"CREATE INDEX IF NOT EXISTS idx_connection_user_profile "
        f"ON {_TEST_SCHEMA}.connection(app_user_id, crawled_profile_id)"
    ))

    # connection: direct policy — rows visible only when app_user_id matches session var
    session.execute(text(f"ALTER TABLE {_TEST_SCHEMA}.connection ENABLE ROW LEVEL SECURITY"))
    session.execute(text(f"ALTER TABLE {_TEST_SCHEMA}.connection FORCE ROW LEVEL SECURITY"))
    session.execute(text(
        f"CREATE POLICY app_user_isolation ON {_TEST_SCHEMA}.connection FOR SELECT "
        f"USING (app_user_id = NULLIF(current_setting('{_SESSION_VAR}', TRUE), ''))"
    ))

    # Profile-linked tables: EXISTS policy via connection table
    for table in _PROFILE_TABLES:
        fk_col = "id" if table == "crawled_profile" else "crawled_profile_id"
        session.execute(text(f"ALTER TABLE {_TEST_SCHEMA}.{table} ENABLE ROW LEVEL SECURITY"))
        session.execute(text(f"ALTER TABLE {_TEST_SCHEMA}.{table} FORCE ROW LEVEL SECURITY"))
        session.execute(text(
            f"CREATE POLICY user_profiles ON {_TEST_SCHEMA}.{table} FOR SELECT "
            f"USING (EXISTS ("
            f"  SELECT 1 FROM {_TEST_SCHEMA}.connection "
            f"  WHERE {_TEST_SCHEMA}.connection.crawled_profile_id = {_TEST_SCHEMA}.{table}.{fk_col} "
            f"  AND {_TEST_SCHEMA}.connection.app_user_id = NULLIF(current_setting('{_SESSION_VAR}', TRUE), '')::uuid"
            f"))"
        ))

    session.commit()

    yield

    # Teardown: remove all RLS so other test modules using the owner connection
    # can query these tables normally again.
    for table in _PROFILE_TABLES:
        session.execute(text(f"DROP POLICY IF EXISTS user_profiles ON {_TEST_SCHEMA}.{table}"))
        session.execute(text(f"ALTER TABLE {_TEST_SCHEMA}.{table} DISABLE ROW LEVEL SECURITY"))
    session.execute(text(f"DROP POLICY IF EXISTS app_user_isolation ON {_TEST_SCHEMA}.connection"))
    session.execute(text(f"ALTER TABLE {_TEST_SCHEMA}.connection DISABLE ROW LEVEL SECURITY"))
    session.execute(text(f"DROP INDEX IF EXISTS {_TEST_SCHEMA}.idx_connection_user_profile"))
    session.commit()

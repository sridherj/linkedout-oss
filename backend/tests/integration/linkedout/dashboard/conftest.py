# SPDX-License-Identifier: Apache-2.0
"""Fixtures for dashboard integration tests.

Creates test data with two users, connections with varied profiles
for testing dashboard aggregation, user isolation, and empty state.
"""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from linkedout.connection.entities.connection_entity import ConnectionEntity
from linkedout.crawled_profile.entities.crawled_profile_entity import CrawledProfileEntity
from organization.entities.app_user_entity import AppUserEntity


@pytest.fixture(scope='session')
def dashboard_test_data(integration_db_session: Session, seeded_data):
    """Create dashboard-specific test data: 2 users with separate connections.

    User A: 20 connections (10 enriched, 10 not).
    User B: 5 connections (all enriched, distinct data).
    User C: 0 connections (for empty-state test).
    """
    session = integration_db_session
    tenant = seeded_data['tenant'][0]
    bu = seeded_data['bu'][0]

    user_a = AppUserEntity(
        email='dash_user_a@test.com',
        name='Dashboard User A',
        auth_provider_id='auth0|dash_a',
    )
    user_b = AppUserEntity(
        email='dash_user_b@test.com',
        name='Dashboard User B',
        auth_provider_id='auth0|dash_b',
    )
    user_c = AppUserEntity(
        email='dash_user_c@test.com',
        name='Dashboard User C',
        auth_provider_id='auth0|dash_c',
    )
    session.add_all([user_a, user_b, user_c])
    session.flush()

    # -- User A: 20 connections --
    functions = ['Engineering', 'Product', 'Design', 'Marketing', 'Sales']
    seniorities = ['Senior', 'Mid', 'Junior', None, 'Senior']
    cities = ['San Francisco', 'New York', 'London', 'Berlin', None]
    companies = ['Google', 'Stripe', 'Notion', 'Figma', None]
    tiers = ['inner_circle', 'sympathy_group', 'hunting_party', 'band', None]

    profiles_a = []
    for i in range(20):
        enriched = i < 10
        p = CrawledProfileEntity(
            linkedin_url=f'https://linkedin.com/in/dash-a-{i}',
            public_identifier=f'dash-a-{i}',
            first_name=f'DashA{i}',
            last_name='Test',
            full_name=f'DashA{i} Test',
            headline=f'Role {i}',
            function_area=functions[i % len(functions)] if enriched else None,
            seniority_level=seniorities[i % len(seniorities)] if enriched else None,
            location_city=cities[i % len(cities)] if enriched else None,
            current_company_name=companies[i % len(companies)] if enriched else None,
            data_source='test',
            has_enriched_data=enriched,
        )
        profiles_a.append(p)
    session.add_all(profiles_a)
    session.flush()

    connections_a = []
    for i, p in enumerate(profiles_a):
        # First 10: both sources; last 10: linkedin only
        sources = ['linkedin', 'gmail'] if i < 10 else ['linkedin']
        c = ConnectionEntity(
            tenant_id=tenant.id,
            bu_id=bu.id,
            app_user_id=user_a.id,
            crawled_profile_id=p.id,
            connected_at=date(2025, 6, 1),
            sources=sources,
            dunbar_tier=tiers[i % len(tiers)] if i < 10 else None,
        )
        connections_a.append(c)
    session.add_all(connections_a)
    session.flush()

    # -- User B: 5 connections (different data) --
    profiles_b = []
    for i in range(5):
        p = CrawledProfileEntity(
            linkedin_url=f'https://linkedin.com/in/dash-b-{i}',
            public_identifier=f'dash-b-{i}',
            first_name=f'DashB{i}',
            last_name='Other',
            full_name=f'DashB{i} Other',
            headline=f'Designer {i}',
            function_area='Design',
            seniority_level='Mid',
            location_city='Tokyo',
            current_company_name='DesignCo',
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

    session.commit()

    return {
        'tenant': tenant,
        'bu': bu,
        'user_a': user_a,
        'user_b': user_b,
        'user_c': user_c,
        'profiles_a': profiles_a,
        'profiles_b': profiles_b,
        'connections_a': connections_a,
        'connections_b': connections_b,
    }

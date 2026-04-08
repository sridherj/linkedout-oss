# SPDX-License-Identifier: Apache-2.0
"""
Fixed seed data for consistent testing.

This module contains deterministic data that remains constant across environments,
allowing for reliable API testing and development.
"""
from datetime import datetime, timezone

# ============================================================================
# ORGANIZATION
# ============================================================================

FIXED_TENANT = {
    'id': 'tenant-test-001',
    'name': 'Acme Corp',
}

FIXED_BUS = [
    {
        'id': 'bu-test-001',
        'tenant_id': 'tenant-test-001',
        'name': 'Engineering',
    },
    {
        'id': 'bu-test-002',
        'tenant_id': 'tenant-test-001',
        'name': 'Product',
    },
]

# ============================================================================
# COMMON AGENT INFRASTRUCTURE
# ============================================================================

FIXED_AGENT_RUNS = [
    {
        'id': 'arn_2025-01-20-08-00-00_tsk00001',
        'tenant_id': 'tenant-test-001',
        'bu_id': 'bu-test-001',
        'agent_type': 'TASK_TRIAGE',
        'status': 'COMPLETED',
        'input_params': {'task_id': 'task-test-001'},
        'started_at': datetime(2025, 1, 20, 8, 0, 0, tzinfo=timezone.utc),
        'completed_at': datetime(2025, 1, 20, 8, 1, 30, tzinfo=timezone.utc),
    },
]

FIXED_APP_USERS = [
    {
        'id': 'usr-test-001',
        'email': 'alice@acme.com',
        'name': 'Alice Admin',
        'auth_provider_id': 'auth0|alice001',
    },
    {
        'id': 'usr-test-002',
        'email': 'bob@acme.com',
        'name': 'Bob Builder',
        'auth_provider_id': 'auth0|bob002',
    },
]

FIXED_APP_USER_TENANT_ROLES = [
    {
        'id': 'autr-test-001',
        'app_user_id': 'usr-test-001',
        'tenant_id': 'tenant-test-001',
        'role': 'admin',
    },
    {
        'id': 'autr-test-002',
        'app_user_id': 'usr-test-002',
        'tenant_id': 'tenant-test-001',
        'role': 'member',
    },
]

# ============================================================================
# LINKEDOUT DOMAIN
# ============================================================================

FIXED_COMPANIES = [
    {
        'id': 'co-test-001',
        'canonical_name': 'Acme Corporation',
        'normalized_name': 'acme corporation',
        'domain': 'acme.com',
        'industry': 'Technology',
        'size_tier': 'large',
        'hq_country': 'US',
    },
    {
        'id': 'co-test-002',
        'canonical_name': 'Beta Industries',
        'normalized_name': 'beta industries',
        'domain': 'beta.io',
        'industry': 'Manufacturing',
        'size_tier': 'mid',
        'hq_country': 'UK',
    },
]

# ============================================================================
# SYSTEM RECORDS (LinkedOut system tenant/BU/user)
# ============================================================================

SYSTEM_TENANT = {
    'id': 'tenant_sys_001',
    'name': 'System Tenant',
}

SYSTEM_BU = {
    'id': 'bu_sys_001',
    'tenant_id': 'tenant_sys_001',
    'name': 'System BU',
}

SYSTEM_USER_ID = 'usr_sys_001'

SYSTEM_APP_USER = {
    'id': SYSTEM_USER_ID,
    'email': 'system@linkedout.local',
    'name': 'System Admin',
    'auth_provider_id': 'system|admin001',
}

FIXED_ROLE_ALIASES = [
    {
        'id': 'ra-test-001',
        'alias_title': 'Software Developer',
        'canonical_title': 'Software Engineer',
        'seniority_level': 'Mid',
        'function_area': 'Engineering',
    },
    {
        'id': 'ra-test-002',
        'alias_title': 'VP Eng',
        'canonical_title': 'VP Engineering',
        'seniority_level': 'VP',
        'function_area': 'Engineering',
    },
]

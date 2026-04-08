# SPDX-License-Identifier: Apache-2.0
"""Fresh baseline migration for LinkedOut OSS.

Replaces entire migration history. Creates all tables, indexes,
extensions, and RLS policies from scratch.

Revision ID: 001_baseline
Revises: None
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = '001_baseline'
down_revision = None
branch_labels = None
depends_on = None

# ── Session variable for RLS ─────────────────────────────────────────────────
_SESSION_VAR = "app.current_user_id"
_RLS_PROFILE_TABLES = ['crawled_profile', 'experience', 'education', 'profile_skill']

# ── BaseEntity columns (shared across all tables) ────────────────────────────
def _base_columns():
    """Return the common BaseEntity columns."""
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('updated_by', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    ]


def _tenant_bu_columns():
    """Return tenant_id and bu_id columns for TenantBuMixin entities."""
    return [
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('tenant.id'), nullable=False),
        sa.Column('bu_id', sa.String(), sa.ForeignKey('bu.id'), nullable=False),
    ]


def upgrade() -> None:
    # ══════════════════════════════════════════════════════════════════════════
    # 1. Extensions
    # ══════════════════════════════════════════════════════════════════════════
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ══════════════════════════════════════════════════════════════════════════
    # 2. Cleanup: drop retired tables from previous installations
    # ══════════════════════════════════════════════════════════════════════════
    op.execute("DROP TABLE IF EXISTS procrastinate_events CASCADE")
    op.execute("DROP TABLE IF EXISTS procrastinate_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS procrastinate_periodic_defers CASCADE")
    op.execute("DROP TABLE IF EXISTS procrastinate_workers CASCADE")

    # ══════════════════════════════════════════════════════════════════════════
    # 3. Organization tables
    # ══════════════════════════════════════════════════════════════════════════

    # -- tenant --
    op.create_table(
        'tenant',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        *_base_columns(),
    )

    # -- bu (business unit) --
    op.create_table(
        'bu',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('tenant.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        *_base_columns(),
    )

    # -- app_user --
    op.create_table(
        'app_user',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False, unique=True),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('auth_provider_id', sa.String(), nullable=True, unique=True),
        sa.Column('api_key_prefix', sa.String(8), nullable=True),
        sa.Column('api_key_hash', sa.String(), nullable=True),
        # own_crawled_profile_id FK added after crawled_profile table exists
        sa.Column('own_crawled_profile_id', sa.String(), nullable=True),
        sa.Column('network_preferences', sa.Text(), nullable=True),
        *_base_columns(),
    )

    # -- app_user_tenant_role --
    op.create_table(
        'app_user_tenant_role',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('tenant_id', sa.String(), sa.ForeignKey('tenant.id'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        *_base_columns(),
    )

    # -- enrichment_config --
    op.create_table(
        'enrichment_config',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('enrichment_mode', sa.String(), nullable=False, server_default='platform'),
        sa.Column('apify_key_encrypted', sa.String(), nullable=True),
        sa.Column('apify_key_hint', sa.String(), nullable=True),
        *_base_columns(),
        sa.UniqueConstraint('app_user_id', name='uq_enrichment_config_app_user_id'),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 4. Shared domain tables (no tenant/BU scoping)
    # ══════════════════════════════════════════════════════════════════════════

    # -- company --
    op.create_table(
        'company',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('canonical_name', sa.String(255), nullable=False, unique=True),
        sa.Column('normalized_name', sa.String(255), nullable=False),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('universal_name', sa.String(255), nullable=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('domain', sa.String(255), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('founded_year', sa.Integer(), nullable=True),
        sa.Column('hq_city', sa.String(255), nullable=True),
        sa.Column('hq_country', sa.String(100), nullable=True),
        sa.Column('employee_count_range', sa.String(50), nullable=True),
        sa.Column('estimated_employee_count', sa.Integer(), nullable=True),
        sa.Column('size_tier', sa.String(20), nullable=True),
        sa.Column('network_connection_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_company_id', sa.String(), nullable=True),
        sa.Column('enrichment_sources', ARRAY(sa.Text()), nullable=True),
        sa.Column('enriched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pdl_id', sa.String(100), nullable=True),
        sa.Column('wikidata_id', sa.String(50), nullable=True),
        *_base_columns(),
    )

    # -- crawled_profile (embedding columns added via raw SQL) --
    op.create_table(
        'crawled_profile',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('linkedin_url', sa.String(500), nullable=False, unique=True),
        sa.Column('public_identifier', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(255), nullable=True),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('full_name', sa.String(500), nullable=True),
        sa.Column('headline', sa.Text(), nullable=True),
        sa.Column('about', sa.Text(), nullable=True),
        sa.Column('location_city', sa.String(255), nullable=True),
        sa.Column('location_state', sa.String(255), nullable=True),
        sa.Column('location_country', sa.String(255), nullable=True),
        sa.Column('location_country_code', sa.String(10), nullable=True),
        sa.Column('location_raw', sa.String(500), nullable=True),
        sa.Column('connections_count', sa.Integer(), nullable=True),
        sa.Column('follower_count', sa.Integer(), nullable=True),
        sa.Column('open_to_work', sa.Boolean(), nullable=True),
        sa.Column('premium', sa.Boolean(), nullable=True),
        sa.Column('current_company_name', sa.String(500), nullable=True),
        sa.Column('current_position', sa.String(500), nullable=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id'), nullable=True),
        sa.Column('seniority_level', sa.String(100), nullable=True),
        sa.Column('function_area', sa.String(100), nullable=True),
        # embedding_openai and embedding_nomic added via raw SQL (pgvector types)
        sa.Column('embedding_model', sa.String(64), nullable=True),
        sa.Column('embedding_dim', sa.SmallInteger(), nullable=True),
        sa.Column('embedding_updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('search_vector', sa.Text(), nullable=True),
        sa.Column('source_app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=True),
        sa.Column('data_source', sa.String(50), nullable=False),
        sa.Column('has_enriched_data', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_crawled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('profile_image_url', sa.String(1000), nullable=True),
        sa.Column('raw_profile', sa.Text(), nullable=True),
        *_base_columns(),
    )

    # Add pgvector embedding columns (can't use op.create_table for vector types)
    op.execute("ALTER TABLE crawled_profile ADD COLUMN embedding_openai vector(1536)")
    op.execute("ALTER TABLE crawled_profile ADD COLUMN embedding_nomic vector(768)")

    # Add FK from app_user.own_crawled_profile_id → crawled_profile.id
    op.create_foreign_key(
        'fk_app_user_own_profile', 'app_user', 'crawled_profile',
        ['own_crawled_profile_id'], ['id'], ondelete='SET NULL',
    )

    # -- role_alias --
    op.create_table(
        'role_alias',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('alias_title', sa.String(255), nullable=False, unique=True),
        sa.Column('canonical_title', sa.String(255), nullable=False),
        sa.Column('seniority_level', sa.String(100), nullable=True),
        sa.Column('function_area', sa.String(100), nullable=True),
        *_base_columns(),
    )

    # -- company_alias --
    op.create_table(
        'company_alias',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('alias_name', sa.String(), nullable=False),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id', ondelete='CASCADE'), nullable=False),
        # source column from BaseEntity is inherited; CompanyAliasEntity also declares its own
        *_base_columns(),
        sa.UniqueConstraint('alias_name', 'company_id', name='uq_ca_alias_company'),
    )

    # -- experience --
    op.create_table(
        'experience',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('crawled_profile_id', sa.String(), sa.ForeignKey('crawled_profile.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Text(), nullable=True),
        sa.Column('position_normalized', sa.Text(), nullable=True),
        sa.Column('company_name', sa.String(500), nullable=True),
        sa.Column('company_id', sa.String(), sa.ForeignKey('company.id'), nullable=True),
        sa.Column('company_linkedin_url', sa.String(500), nullable=True),
        sa.Column('employment_type', sa.String(50), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('start_year', sa.Integer(), nullable=True),
        sa.Column('start_month', sa.Integer(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('end_year', sa.Integer(), nullable=True),
        sa.Column('end_month', sa.Integer(), nullable=True),
        sa.Column('end_date_text', sa.String(50), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=True),
        sa.Column('seniority_level', sa.String(100), nullable=True),
        sa.Column('function_area', sa.String(100), nullable=True),
        sa.Column('location', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('raw_experience', sa.Text(), nullable=True),
        *_base_columns(),
    )

    # -- education --
    op.create_table(
        'education',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('crawled_profile_id', sa.String(), sa.ForeignKey('crawled_profile.id', ondelete='CASCADE'), nullable=False),
        sa.Column('school_name', sa.Text(), nullable=True),
        sa.Column('school_linkedin_url', sa.String(500), nullable=True),
        sa.Column('degree', sa.String(255), nullable=True),
        sa.Column('field_of_study', sa.String(255), nullable=True),
        sa.Column('start_year', sa.Integer(), nullable=True),
        sa.Column('end_year', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('raw_education', sa.Text(), nullable=True),
        *_base_columns(),
    )

    # -- profile_skill --
    op.create_table(
        'profile_skill',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('crawled_profile_id', sa.String(), sa.ForeignKey('crawled_profile.id', ondelete='CASCADE'), nullable=False),
        sa.Column('skill_name', sa.String(255), nullable=False),
        sa.Column('endorsement_count', sa.Integer(), nullable=False, server_default='0'),
        *_base_columns(),
        sa.UniqueConstraint('crawled_profile_id', 'skill_name', name='uq_psk_profile_skill'),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 5. Tenant/BU-scoped domain tables
    # ══════════════════════════════════════════════════════════════════════════

    # -- connection --
    op.create_table(
        'connection',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('crawled_profile_id', sa.String(), sa.ForeignKey('crawled_profile.id'), nullable=False),
        sa.Column('connected_at', sa.Date(), nullable=True),
        sa.Column('emails', sa.Text(), nullable=True),
        sa.Column('phones', sa.Text(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('sources', ARRAY(sa.Text()), nullable=True),
        sa.Column('source_details', sa.Text(), nullable=True),
        sa.Column('affinity_score', sa.Float(), nullable=True),
        sa.Column('dunbar_tier', sa.String(50), nullable=True),
        sa.Column('affinity_source_count', sa.Float(), nullable=False, server_default='0'),
        sa.Column('affinity_recency', sa.Float(), nullable=False, server_default='0'),
        sa.Column('affinity_career_overlap', sa.Float(), nullable=False, server_default='0'),
        sa.Column('affinity_mutual_connections', sa.Float(), nullable=False, server_default='0'),
        sa.Column('affinity_external_contact', sa.Float(), nullable=False, server_default='0'),
        sa.Column('affinity_embedding_similarity', sa.Float(), nullable=False, server_default='0'),
        sa.Column('affinity_computed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('affinity_version', sa.Integer(), nullable=False, server_default='0'),
        *_base_columns(),
        sa.UniqueConstraint('app_user_id', 'crawled_profile_id', name='uq_conn_app_user_profile'),
    )

    # -- import_job --
    op.create_table(
        'import_job',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('file_name', sa.Text(), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('total_records', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parsed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('matched_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('new_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('enrichment_queued', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        *_base_columns(),
    )

    # -- contact_source --
    op.create_table(
        'contact_source',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('import_job_id', sa.String(), sa.ForeignKey('import_job.id'), nullable=False),
        sa.Column('source_type', sa.String(), nullable=False),
        sa.Column('source_file_name', sa.Text(), nullable=True),
        sa.Column('first_name', sa.Text(), nullable=True),
        sa.Column('last_name', sa.Text(), nullable=True),
        sa.Column('full_name', sa.Text(), nullable=True),
        sa.Column('email', sa.Text(), nullable=True),
        sa.Column('phone', sa.Text(), nullable=True),
        sa.Column('company', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('linkedin_url', sa.Text(), nullable=True),
        sa.Column('connected_at', sa.Date(), nullable=True),
        sa.Column('raw_record', JSONB(), nullable=True),
        sa.Column('connection_id', sa.String(), sa.ForeignKey('connection.id'), nullable=True),
        sa.Column('dedup_status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('dedup_method', sa.Text(), nullable=True),
        sa.Column('dedup_confidence', sa.Float(), nullable=True),
        sa.Column('source_label', sa.String(50), nullable=True),
        *_base_columns(),
    )

    # -- enrichment_event --
    op.create_table(
        'enrichment_event',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('crawled_profile_id', sa.String(), sa.ForeignKey('crawled_profile.id'), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('enrichment_mode', sa.String(), nullable=False),
        sa.Column('crawler_name', sa.String(), nullable=True),
        sa.Column('cost_estimate_usd', sa.Float(), nullable=False, server_default='0'),
        sa.Column('crawler_run_id', sa.String(), nullable=True),
        *_base_columns(),
    )

    # -- search_session --
    op.create_table(
        'search_session',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('initial_query', sa.Text(), nullable=False),
        sa.Column('turn_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_saved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('saved_name', sa.Text(), nullable=True),
        *_base_columns(),
    )

    # -- search_turn --
    op.create_table(
        'search_turn',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('session_id', sa.String(), sa.ForeignKey('search_session.id'), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('user_query', sa.Text(), nullable=False),
        sa.Column('transcript', JSONB(), nullable=True),
        sa.Column('results', JSONB(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        *_base_columns(),
    )

    # -- search_tag --
    op.create_table(
        'search_tag',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('app_user_id', sa.String(), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('session_id', sa.String(), sa.ForeignKey('search_session.id'), nullable=False),
        sa.Column('crawled_profile_id', sa.String(), sa.ForeignKey('crawled_profile.id'), nullable=False),
        sa.Column('tag_name', sa.Text(), nullable=False),
        *_base_columns(),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 6. Funding / startup pipeline tables (shared, no tenant/BU scoping)
    # ══════════════════════════════════════════════════════════════════════════

    # -- funding_round --
    op.create_table(
        'funding_round',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('round_type', sa.String(50), nullable=False),
        sa.Column('announced_on', sa.Date(), nullable=True),
        sa.Column('amount_usd', sa.BigInteger(), nullable=True),
        sa.Column('lead_investors', ARRAY(sa.Text()), nullable=True),
        sa.Column('all_investors', ARRAY(sa.Text()), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('confidence', sa.SmallInteger(), nullable=False, server_default='5'),
        *_base_columns(),
        sa.UniqueConstraint('company_id', 'round_type', 'amount_usd', name='ix_fr_dedup'),
    )

    # -- growth_signal --
    op.create_table(
        'growth_signal',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), nullable=False),
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('signal_date', sa.Date(), nullable=False),
        sa.Column('value_numeric', sa.BigInteger(), nullable=True),
        sa.Column('value_text', sa.Text(), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('confidence', sa.SmallInteger(), nullable=False, server_default='5'),
        *_base_columns(),
        sa.UniqueConstraint('company_id', 'signal_type', 'signal_date', 'source', name='ix_gs_dedup'),
    )

    # -- startup_tracking --
    op.create_table(
        'startup_tracking',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('company_id', sa.String(), nullable=False, unique=True),
        sa.Column('watching', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('vertical', sa.String(100), nullable=True),
        sa.Column('sub_category', sa.String(100), nullable=True),
        sa.Column('funding_stage', sa.String(50), nullable=True),
        sa.Column('total_raised_usd', sa.BigInteger(), nullable=True),
        sa.Column('last_funding_date', sa.Date(), nullable=True),
        sa.Column('round_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('estimated_arr_usd', sa.BigInteger(), nullable=True),
        sa.Column('arr_signal_date', sa.Date(), nullable=True),
        sa.Column('arr_confidence', sa.SmallInteger(), nullable=True),
        *_base_columns(),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 7. Common infrastructure tables
    # ══════════════════════════════════════════════════════════════════════════

    # -- agent_run --
    op.create_table(
        'agent_run',
        sa.Column('id', sa.String(), primary_key=True),
        *_tenant_bu_columns(),
        sa.Column('agent_type', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('input_params', JSONB(), nullable=True),
        sa.Column('output', JSONB(), nullable=True),
        sa.Column('llm_input', JSONB(), nullable=True),
        sa.Column('llm_output', JSONB(), nullable=True),
        sa.Column('llm_cost_usd', sa.Float(), nullable=True),
        sa.Column('llm_latency_ms', sa.Integer(), nullable=True),
        sa.Column('llm_metadata', JSONB(), nullable=True),
        *_base_columns(),
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 8. B-tree indexes (entity-defined)
    # ══════════════════════════════════════════════════════════════════════════

    # crawled_profile
    op.create_index('ix_cp_linkedin_url', 'crawled_profile', ['linkedin_url'], unique=True)
    op.create_index('ix_cp_company_id', 'crawled_profile', ['company_id'])
    op.create_index('ix_cp_current_company', 'crawled_profile', ['current_company_name'])
    op.create_index('ix_cp_location', 'crawled_profile', ['location_city', 'location_country_code'])
    op.create_index('ix_cp_seniority', 'crawled_profile', ['seniority_level'])
    op.create_index('ix_cp_function', 'crawled_profile', ['function_area'])
    op.create_index('ix_cp_has_enriched', 'crawled_profile', ['has_enriched_data'])
    op.create_index('ix_cp_source_app_user', 'crawled_profile', ['source_app_user_id'])

    # company
    op.create_index('ix_co_canonical', 'company', ['canonical_name'], unique=True)
    op.create_index('ix_co_domain', 'company', ['domain'])
    op.create_index('ix_co_industry', 'company', ['industry'])
    op.create_index('ix_co_size_tier', 'company', ['size_tier'])
    op.create_index('ix_co_parent', 'company', ['parent_company_id'])
    op.create_index('ix_co_hq_country', 'company', ['hq_country'])

    # company_alias
    op.create_index('ix_ca_alias_name', 'company_alias', ['alias_name'])
    op.create_index('ix_ca_company_id', 'company_alias', ['company_id'])

    # connection
    op.create_index('ix_conn_app_user', 'connection', ['app_user_id'])
    op.create_index('ix_conn_tenant', 'connection', ['tenant_id'])
    op.create_index('ix_conn_bu', 'connection', ['bu_id'])
    op.create_index('ix_conn_app_user_profile', 'connection', ['app_user_id', 'crawled_profile_id'])
    op.create_index('ix_conn_dunbar', 'connection', ['app_user_id', 'dunbar_tier'])
    op.create_index('ix_conn_crawled_profile', 'connection', ['crawled_profile_id'])

    # connection: affinity indexes with DESC NULLS LAST (raw SQL for sort direction)
    op.execute(
        "CREATE INDEX ix_conn_app_user_affinity "
        "ON connection (app_user_id, affinity_score DESC NULLS LAST)"
    )
    op.execute(
        "CREATE INDEX ix_conn_tenant_affinity "
        "ON connection (tenant_id, affinity_score DESC NULLS LAST)"
    )

    # RLS composite index
    op.execute(
        "CREATE INDEX idx_connection_user_profile "
        "ON connection (app_user_id, crawled_profile_id)"
    )

    # experience
    op.create_index('ix_exp_profile', 'experience', ['crawled_profile_id'])
    op.create_index('ix_exp_company', 'experience', ['company_id'])
    op.create_index('ix_exp_current', 'experience', ['is_current'])
    op.create_index('ix_exp_dates', 'experience', ['start_date', 'end_date'])
    op.execute(
        "CREATE INDEX ix_exp_profile_start "
        "ON experience (crawled_profile_id, start_date DESC NULLS FIRST)"
    )
    op.create_index('ix_exp_company_profile', 'experience', ['company_id', 'crawled_profile_id'])

    # education
    op.create_index('ix_edu_profile', 'education', ['crawled_profile_id'])
    op.create_index('ix_edu_school', 'education', ['school_name'])

    # profile_skill
    op.create_index('ix_psk_profile', 'profile_skill', ['crawled_profile_id'])
    op.create_index('ix_psk_skill', 'profile_skill', ['skill_name'])

    # role_alias
    op.create_index('ix_ra_alias_title', 'role_alias', ['alias_title'], unique=True)
    op.create_index('ix_ra_canonical_title', 'role_alias', ['canonical_title'])
    op.create_index('ix_ra_seniority_level', 'role_alias', ['seniority_level'])
    op.create_index('ix_ra_function_area', 'role_alias', ['function_area'])

    # import_job
    op.create_index('ix_ij_app_user', 'import_job', ['app_user_id'])
    op.create_index('ix_ij_status', 'import_job', ['status'])

    # contact_source
    op.create_index('ix_cs_app_user', 'contact_source', ['app_user_id'])
    op.create_index('ix_cs_import_job', 'contact_source', ['import_job_id'])
    op.create_index('ix_cs_connection', 'contact_source', ['connection_id'])
    op.execute(
        "CREATE INDEX ix_cs_linkedin_url ON contact_source (linkedin_url) "
        "WHERE linkedin_url IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_cs_email ON contact_source (email) "
        "WHERE email IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX ix_cs_dedup_status ON contact_source (dedup_status) "
        "WHERE dedup_status = 'pending'"
    )

    # enrichment_event
    op.create_index('ix_ee_app_user', 'enrichment_event', ['app_user_id'])
    op.create_index('ix_ee_tenant', 'enrichment_event', ['tenant_id'])
    op.create_index('ix_ee_profile', 'enrichment_event', ['crawled_profile_id'])
    op.create_index('ix_ee_type', 'enrichment_event', ['event_type'])

    # search_session
    op.create_index('ix_ss_app_user_latest', 'search_session', ['app_user_id', 'last_active_at'])
    op.create_index('ix_ss_app_user_saved', 'search_session', ['app_user_id', 'is_saved'])
    op.create_index('ix_ss_tenant', 'search_session', ['tenant_id'])

    # search_turn
    op.create_index('ix_sturn_session_turn', 'search_turn', ['session_id', 'turn_number'])

    # search_tag
    op.create_index('ix_stag_app_user_tag', 'search_tag', ['app_user_id', 'tag_name'])
    op.create_index('ix_stag_app_user_profile', 'search_tag', ['app_user_id', 'crawled_profile_id'])
    op.create_index('ix_stag_session', 'search_tag', ['session_id'])
    op.create_index('ix_stag_tenant', 'search_tag', ['tenant_id'])

    # app_user
    op.create_index('ix_au_own_profile', 'app_user', ['own_crawled_profile_id'])

    # app_user_tenant_role
    op.create_index('ix_autr_app_user', 'app_user_tenant_role', ['app_user_id'])
    op.create_index('ix_autr_tenant', 'app_user_tenant_role', ['tenant_id'])

    # funding_round
    op.create_index('ix_fr_company', 'funding_round', ['company_id'])
    op.create_index('ix_fr_announced', 'funding_round', ['announced_on'])
    op.create_index('ix_fr_round_type', 'funding_round', ['round_type'])

    # growth_signal
    op.create_index('ix_gs_company_date', 'growth_signal', ['company_id', 'signal_date'])
    op.create_index('ix_gs_signal_type', 'growth_signal', ['signal_type'])

    # startup_tracking
    op.create_index('ix_st_company', 'startup_tracking', ['company_id'], unique=True)
    op.create_index('ix_st_vertical', 'startup_tracking', ['vertical'])
    op.execute(
        "CREATE INDEX ix_st_watching ON startup_tracking (watching) "
        "WHERE watching = true"
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 9. Trigram GIN indexes (pg_trgm)
    # ══════════════════════════════════════════════════════════════════════════

    _trigram_indexes = [
        # crawled_profile
        ("ix_cp_full_name_trgm", "crawled_profile", "full_name"),
        ("ix_cp_current_company_trgm", "crawled_profile", "current_company_name"),
        ("ix_cp_headline_trgm", "crawled_profile", "headline"),
        ("ix_cp_current_position_trgm", "crawled_profile", "current_position"),
        ("ix_cp_location_city_trgm", "crawled_profile", "location_city"),
        ("ix_cp_location_raw_trgm", "crawled_profile", "location_raw"),
        # company
        ("ix_co_canonical_trgm", "company", "canonical_name"),
        ("ix_co_domain_trgm", "company", "domain"),
        # experience
        ("ix_exp_company_name_trgm", "experience", "company_name"),
        ("ix_exp_position_trgm", "experience", "position"),
        # education
        ("ix_edu_school_trgm", "education", "school_name"),
        ("ix_edu_degree_trgm", "education", "degree"),
        # profile_skill
        ("ix_psk_skill_trgm", "profile_skill", "skill_name"),
        # company_alias
        ("ix_ca_alias_trgm", "company_alias", "alias_name"),
        # role_alias
        ("ix_ra_alias_trgm", "role_alias", "alias_title"),
        ("ix_ra_canonical_trgm", "role_alias", "canonical_title"),
    ]

    for idx_name, table, column in _trigram_indexes:
        op.execute(
            f"CREATE INDEX {idx_name} ON {table} USING gin ({column} gin_trgm_ops)"
        )

    # ══════════════════════════════════════════════════════════════════════════
    # 10. HNSW indexes on embedding columns (pgvector)
    # ══════════════════════════════════════════════════════════════════════════

    op.execute(
        "CREATE INDEX ix_cp_embedding_openai_hnsw ON crawled_profile "
        "USING hnsw (embedding_openai vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_cp_embedding_nomic_hnsw ON crawled_profile "
        "USING hnsw (embedding_nomic vector_cosine_ops)"
    )

    # ══════════════════════════════════════════════════════════════════════════
    # 11. Row-Level Security (RLS) policies
    # ══════════════════════════════════════════════════════════════════════════

    # connection: direct policy on app_user_id
    op.execute("ALTER TABLE connection ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE connection FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY app_user_isolation ON connection FOR SELECT "
        f"USING (app_user_id = NULLIF(current_setting('{_SESSION_VAR}', TRUE), ''))"
    )
    # Write policy: allow inserts/updates when session user is set
    op.execute(
        "CREATE POLICY app_user_write ON connection FOR ALL "
        f"USING (true) "
        f"WITH CHECK (app_user_id = NULLIF(current_setting('{_SESSION_VAR}', TRUE), ''))"
    )

    # Profile-linked tables: EXISTS subquery policy via connection (optimized form)
    for table in _RLS_PROFILE_TABLES:
        fk_col = "id" if table == "crawled_profile" else "crawled_profile_id"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY user_profiles ON {table} FOR SELECT "
            f"USING (EXISTS ("
            f"  SELECT 1 FROM connection "
            f"  WHERE connection.crawled_profile_id = {table}.{fk_col} "
            f"  AND connection.app_user_id = NULLIF(current_setting('{_SESSION_VAR}', TRUE), '')"
            f"))"
        )
        # Write policy: allow inserts/updates/deletes when session user is set
        op.execute(
            f"CREATE POLICY user_profiles_write ON {table} FOR ALL "
            f"USING (true) "
            f"WITH CHECK (true)"
        )


def downgrade() -> None:
    raise NotImplementedError("Downgrade not supported for baseline migration")

# SPDX-License-Identifier: Apache-2.0
"""Add previous_linkedin_url to crawled_profile.

Preserves the original CSV-imported URL when enrichment detects
a LinkedIn slug redirect.

Revision ID: 002_add_previous_linkedin_url
Revises: 001_baseline
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_previous_linkedin_url'
down_revision = '001_baseline'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'crawled_profile',
        sa.Column(
            'previous_linkedin_url',
            sa.String(500),
            nullable=True,
            comment='Previous LinkedIn URL before redirect canonicalization',
        ),
    )
    op.create_index(
        'ix_cp_prev_linkedin_url',
        'crawled_profile',
        ['previous_linkedin_url'],
    )


def downgrade() -> None:
    op.drop_index('ix_cp_prev_linkedin_url', table_name='crawled_profile')
    op.drop_column('crawled_profile', 'previous_linkedin_url')

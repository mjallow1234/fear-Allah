"""Stub for missing notification engine migration

Revision ID: 012_notification_engine
Revises: 011
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "012_notification_engine"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    # no-op stub to repair migration graph
    pass


def downgrade():
    pass

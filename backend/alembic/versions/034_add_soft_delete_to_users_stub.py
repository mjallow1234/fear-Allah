"""Stub for missing soft delete migration

Revision ID: 034_add_soft_delete_to_users
Revises: 29a0528ad237
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "034_add_soft_delete_to_users"
down_revision = "29a0528ad237"
branch_labels = None
depends_on = None


def upgrade():
    # no-op stub to repair migration graph
    pass


def downgrade():
    pass

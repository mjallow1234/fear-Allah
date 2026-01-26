"""Merge 00075132de7f and 039_add_created_by_to_orders

Revision ID: merge_00075132_and_039_add_created_by_to_orders
Revises: 00075132de7f, 039_add_created_by_to_orders
Create Date: 2026-01-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_00075132_and_039_add_created_by_to_orders'
down_revision = ('00075132de7f', '039_add_created_by_to_orders')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge migration: no schema changes required
    pass


def downgrade() -> None:
    # No-op downgrade for merge
    pass

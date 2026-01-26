"""merge multiple heads

Revision ID: 888a6451e2fb
Revises: 00075132de7f, 039_add_created_by_to_orders
Create Date: 2026-01-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '888a6451e2fb'
down_revision = ('00075132de7f', '039_add_created_by_to_orders')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration to unify multiple heads into a single linear history.
    # No schema operations required.
    pass


def downgrade():
    # Downgrade is a no-op; splitting merged heads back is not supported here.
    pass

"""merge alembic heads after operational roles

Revision ID: 042_merge_041_and_90fb72034596
Revises: 041_add_user_operational_roles, 90fb72034596
Create Date: 2026-01-28 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '042_merge_041_and_90fb72034596'
down_revision = ('041_add_user_operational_roles', '90fb72034596')
branch_labels = None
depends_on = None


def upgrade():
    # Merge-only revision: no schema changes.
    pass


def downgrade():
    # No-op downgrade for merge revision
    pass

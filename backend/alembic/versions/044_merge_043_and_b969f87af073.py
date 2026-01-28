"""merge 043 and b969f87af073

Revision ID: 044_merge_043_and_b969f87af073
Revises: 043_merge_all_heads, b969f87af073
Create Date: 2026-01-28 00:10:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '044_merge_043_and_b969f87af073'
down_revision = ('043_merge_all_heads', 'b969f87af073')
branch_labels = None
depends_on = None


def upgrade():
    # Merge-only revision: no schema changes.
    pass


def downgrade():
    # No-op downgrade for merge revision
    pass

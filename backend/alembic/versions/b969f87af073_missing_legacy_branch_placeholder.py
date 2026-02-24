"""placeholder for missing legacy branch

Revision ID: b969f87af073
Revises: 054_add_user_preferences
Create Date: 2026-02-19 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b969f87af073'
down_revision = '054_add_user_preferences'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Placeholder merge/no-op to repair missing legacy branch referenced by other revisions.
    pass


def downgrade() -> None:
    pass

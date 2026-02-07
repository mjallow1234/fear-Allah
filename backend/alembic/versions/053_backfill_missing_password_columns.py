"""backfill missing password columns

Revision ID: 053_backfill_missing_password_columns
Revises: 052
Create Date: 2026-02-07

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '053_backfill_missing_password_columns'
down_revision = '052'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
    """)
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;
    """)


def downgrade():
    # NO-OP: never drop user security columns in production
    pass

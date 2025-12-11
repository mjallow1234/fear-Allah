"""Add system_admin to userrole enum

Revision ID: 005
Revises: 004
Create Date: 2025-12-09
"""
from alembic import op

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Add system_admin to the userrole enum if it doesn't already exist.
    # Use a DO block to check pg_type/pg_enum and only add if missing to keep migrations idempotent.
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        WHERE t.typname = 'userrole' AND e.enumlabel = 'system_admin'
      ) THEN
        EXECUTE 'ALTER TYPE userrole ADD VALUE ''system_admin''';
      END IF;
    END
    $$;
    """)


def downgrade():
    # Removing an enum label is not supported safely across Postgres versions and may break data.
    # We intentionally leave downgrade as a no-op.
    pass

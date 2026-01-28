"""add task_claimed to taskeventtype enum

Revision ID: 046_add_task_claimed_event
Revises: 045_backfill_user_operational_roles
Create Date: 2026-01-28 00:40:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "046_add_task_claimed_event"
down_revision = "045_backfill_user_operational_roles"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL ENUM extension (safe + idempotent)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_enum
            WHERE enumlabel = 'task_claimed'
              AND enumtypid = 'taskeventtype'::regtype
        ) THEN
            ALTER TYPE taskeventtype ADD VALUE 'task_claimed';
        END IF;
    END$$;
    """)


def downgrade():
    # Cannot remove enum values safely in Postgres
    pass

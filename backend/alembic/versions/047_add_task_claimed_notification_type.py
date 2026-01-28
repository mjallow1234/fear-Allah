"""add task_claimed to notificationtype enum

Revision ID: 047_add_task_claimed_notification_type
Revises: 046_add_task_claimed_event
Create Date: 2026-01-28 00:50:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "047_add_task_claimed_notification_type"
down_revision = "046_add_task_claimed_event"
branch_labels = None
depends_on = None


def upgrade():
    """Extend the Postgres enum with the missing value.

    This migration is schema-only and idempotent. It is skipped on non-Postgres
    databases (e.g., SQLite used in tests) to avoid dialect errors.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Non-Postgres dialects (like SQLite) do not need this change.
        return

    # Use Postgres ALTER TYPE ... ADD VALUE IF NOT EXISTS for idempotence.
    op.execute("""
    ALTER TYPE notificationtype
    ADD VALUE IF NOT EXISTS 'task_claimed';
    """)


def downgrade():
    # Removing enum values is unsafe in Postgres and is intentionally a no-op.
    pass

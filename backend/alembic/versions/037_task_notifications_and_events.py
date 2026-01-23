"""Add task notification and event enum values

Revision ID: 037_task_notifications_and_events
Revises: 036_claimable_tasks
Create Date: 2026-01-23
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '037_task_notifications_and_events'
down_revision = '036_claimable_tasks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new notification types
    op.execute("DO $$ BEGIN ALTER TYPE notificationtype ADD VALUE 'task_opened'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN ALTER TYPE notificationtype ADD VALUE 'task_claimed'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # Add new task event types
    op.execute("DO $$ BEGIN ALTER TYPE taskeventtype ADD VALUE 'task_opened'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN ALTER TYPE taskeventtype ADD VALUE 'task_claimed'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN ALTER TYPE taskeventtype ADD VALUE 'task_reassigned'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")


def downgrade() -> None:
    # NOTE: removing enum labels is unsafe and not attempted here. They remain for forward compatibility.
    pass

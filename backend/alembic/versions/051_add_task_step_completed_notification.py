"""add task_step_completed to notificationtype enum

Revision ID: 051_add_task_step_completed_notification
Revises: 050_fix_is_order_root_data
Create Date: 2026-02-03 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "051_add_task_step_completed_notification"
down_revision = "050_fix_is_order_root_data"
branch_labels = None
depends_on = None


def upgrade():
    # Add the new enum value to Postgres notificationtype enum
    # Using IF NOT EXISTS for idempotency (safe to re-run)
    op.execute(
        "ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'task_step_completed';"
    )


def downgrade():
    # Postgres does not support removing enum values safely
    # This is a known Postgres limitation
    pass

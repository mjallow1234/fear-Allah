"""Make task_assignments.user_id nullable

Revision ID: 038_make_task_assignment_user_nullable
Revises: 037_task_notifications_and_events
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '038_make_task_assignment_user_nullable'
down_revision = '037_task_notifications_and_events'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "task_assignments",
        "user_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "task_assignments",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

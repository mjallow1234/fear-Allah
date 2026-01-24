"""merge task_notifications and audit_logs

Revision ID: 00015132de1d
Revises: 037_task_notifications_and_events, add_audit_logs_table
Create Date: 2026-01-24 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00015132de1d"
down_revision: Union[str, Sequence[str], None] = ("037_task_notifications_and_events", "add_audit_logs_table")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

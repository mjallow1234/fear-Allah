"""add claimed_by_user_id and claimed_at to automation_tasks

Revision ID: 00075132de7f
Revises: 00065132de6e
Create Date: 2026-01-24 21:45:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00075132de7f"
down_revision: Union[str, Sequence[str], None] = "00065132de6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "automation_tasks",
        sa.Column("claimed_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "automation_tasks",
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_tasks", "claimed_at")
    op.drop_column("automation_tasks", "claimed_by_user_id")

"""add required_role to automation_tasks

Revision ID: 00055132de5d
Revises: 00045132de4c
Create Date: 2026-01-24 21:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00055132de5d"
down_revision: Union[str, Sequence[str], None] = "00045132de4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "automation_tasks",
        sa.Column("required_role", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_tasks", "required_role")

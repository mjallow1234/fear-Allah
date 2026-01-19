"""Make users.operational_role nullable

Revision ID: 035_make_operational_role_nullable
Revises: 034_add_soft_delete_to_users
Create Date: 2026-01-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '035_make_operational_role_nullable'
down_revision = '034_add_soft_delete_to_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "operational_role",
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "operational_role",
        nullable=False,
    )

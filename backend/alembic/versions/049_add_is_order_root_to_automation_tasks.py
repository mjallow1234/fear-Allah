"""add is_order_root column and unique partial index for order root automation task

Revision ID: 049_add_is_order_root_to_automation_tasks
Revises: 048_add_system_user_id_0
Create Date: 2026-02-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "049_add_is_order_root_to_automation_tasks"
down_revision = "048_add_system_user_id_0"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Add the column with a safe server default to avoid NULLs for existing rows.
    op.add_column(
        "automation_tasks",
        sa.Column("is_order_root", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # For PostgreSQL create a partial unique index to ensure only one order-root automation task per order
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_order_root_per_order",
            "automation_tasks",
            ["related_order_id"],
            unique=True,
            postgresql_where=sa.text("is_order_root = true"),
        )


def downgrade():
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.drop_index("uq_order_root_per_order", table_name="automation_tasks")

    op.drop_column("automation_tasks", "is_order_root")

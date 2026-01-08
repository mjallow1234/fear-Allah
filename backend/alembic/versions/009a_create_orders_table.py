"""Create orders table (required for automation engine)

Revision ID: 009a
Revises: 009
Create Date: 2026-01-06
"""

from alembic import op
import sqlalchemy as sa

revision = "009a"
down_revision = "f93a4f97e6d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="submitted"),
        sa.Column("meta", sa.Text()),
        sa.Column("items", sa.Text()),
        sa.Column("reference", sa.String(100)),
        sa.Column("priority", sa.String(20)),
        sa.Column("requested_delivery_date", sa.DateTime(timezone=True)),
        sa.Column("customer_name", sa.String(200)),
        sa.Column("customer_phone", sa.String(50)),
        sa.Column("payment_method", sa.String(50)),
        sa.Column("internal_comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("orders")

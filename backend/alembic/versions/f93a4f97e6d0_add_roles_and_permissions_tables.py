"""add roles and permissions tables

Revision ID: f93a4f97e6d0
Revises: 009_add_channel_reads
Create Date: 2025-12-24 17:37:35.854376

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f93a4f97e6d0'
down_revision: str = '009'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("scope", sa.String, nullable=False),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", sa.Integer, sa.ForeignKey("permissions.id"), primary_key=True),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), primary_key=True),
    )

    op.create_table(
        "channel_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), primary_key=True),
    )


def downgrade():
    op.drop_table("channel_roles")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")

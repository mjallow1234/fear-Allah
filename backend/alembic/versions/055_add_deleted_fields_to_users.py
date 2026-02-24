"""add deleted_at and deleted_by_id to users

Revision ID: 055_add_deleted_fields_to_users
Revises: 054_add_user_preferences
Create Date: 2026-02-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '055_add_deleted_fields_to_users'
down_revision = '054_add_user_preferences'
branch_labels = None
depends_on = None


def upgrade():
    # add soft-delete columns to users
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('deleted_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))


def downgrade():
    op.drop_column('users', 'deleted_by_id')
    op.drop_column('users', 'deleted_at')

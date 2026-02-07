"""add password management fields to user

Revision ID: 052
Revises: 051
Create Date: 2026-02-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '052'
down_revision = '051_add_task_step_completed_notification'
branch_labels = None
depends_on = None


def upgrade():
    # Add password management fields to users table
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove password management fields
    op.drop_column('users', 'must_change_password')
    op.drop_column('users', 'password_changed_at')
    op.drop_column('users', 'last_login_at')

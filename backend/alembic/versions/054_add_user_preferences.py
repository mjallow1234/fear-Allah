"""add user preferences JSONB column

Revision ID: 054_add_user_preferences
Revises: 053_backfill_missing_password_columns
Create Date: 2026-02-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '054_add_user_preferences'
down_revision = '053_backfill_missing_password_columns'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('preferences', JSONB, nullable=True))


def downgrade():
    op.drop_column('users', 'preferences')

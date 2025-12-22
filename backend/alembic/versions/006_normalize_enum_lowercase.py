"""normalize enums to include lowercase labels

Revision ID: 006_normalize_enum_lowercase
Revises: 005_add_system_admin_enum
Create Date: 2025-12-11 13:40:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_normalize_enum_lowercase'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add lowercase enum labels if they don't exist
    # userstatus enum
    op.execute("""
    DO $$ BEGIN
        ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'online';
        ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'offline';
        ALTER TYPE userstatus ADD VALUE IF NOT EXISTS 'away';
    EXCEPTION WHEN duplicate_object THEN null; END; $$;
    """)
    # channeltype enum
    op.execute("""
    DO $$ BEGIN
        ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'direct';
        ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'public';
        ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'private';
    EXCEPTION WHEN duplicate_object THEN null; END; $$;
    """)
    # userrole enum
    op.execute("""
    DO $$ BEGIN
        ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'member';
        ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'team_admin';
        ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'system_admin';
        ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'guest';
    EXCEPTION WHEN duplicate_object THEN null; END; $$;
    """)


def downgrade() -> None:
    # No-op for downgrade for now, cannot safely remove enum labels
    pass

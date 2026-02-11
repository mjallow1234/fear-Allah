"""add chat notification enum values

Revision ID: 059_add_chat_notification_enum_values
Revises: 058_add_direct_conversation_reads
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '059_add_chat_notification_enum_values'
down_revision = '058_add_direct_conversation_reads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new labels to notificationtype enum without recreating or reordering
    op.execute("""
    DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtype') THEN
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'dm_message';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'dm_reply';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'channel_reply';
        END IF;
    EXCEPTION WHEN duplicate_object THEN null; END; $$;
    """)


def downgrade() -> None:
    # No-op: removing enum values is unsafe in Postgres; do not attempt to drop values
    pass

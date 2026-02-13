"""add indexes for activity-based ordering

Revision ID: 090_add_last_activity_indexes
Revises: 059_add_chat_notification_enum_values
Create Date: 2026-02-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '090_add_last_activity_indexes'
down_revision = '059_add_chat_notification_enum_values'
branch_labels = None
depends_on = None


def upgrade():
    # index to support channel activity ordering queries
    op.create_index('ix_messages_channel_last_activity', 'messages', ['channel_id', 'last_activity_at', 'created_at'], unique=False)
    # index to support direct conversation activity ordering queries
    op.create_index('ix_messages_direct_last_activity', 'messages', ['direct_conversation_id', 'last_activity_at', 'created_at'], unique=False)


def downgrade():
    op.drop_index('ix_messages_direct_last_activity', table_name='messages')
    op.drop_index('ix_messages_channel_last_activity', table_name='messages' )
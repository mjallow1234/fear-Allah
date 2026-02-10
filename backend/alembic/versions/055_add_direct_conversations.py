"""add direct conversations and link messages

Revision ID: 055_add_direct_conversations
Revises: 054_add_user_preferences
Create Date: 2026-02-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '055_add_direct_conversations'
down_revision = '054_add_user_preferences'
branch_labels = None
depends_on = None


def upgrade():
    # Create direct_conversations table
    op.create_table(
        'direct_conversations',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('participant_pair', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index(op.f('ix_direct_conversations_id'), 'direct_conversations', ['id'], unique=False)
    op.create_unique_constraint('uq_direct_conversation_pair', 'direct_conversations', ['participant_pair'])

    # Create direct_conversation_participants table
    op.create_table(
        'direct_conversation_participants',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('direct_conversation_id', sa.Integer(), sa.ForeignKey('direct_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_direct_conv_participant', 'direct_conversation_participants', ['direct_conversation_id', 'user_id'])

    # Add direct_conversation_id to messages (nullable)
    op.add_column('messages', sa.Column('direct_conversation_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_messages_direct_conversation', 'messages', 'direct_conversations', ['direct_conversation_id'], ['id'])

    # Add check constraint to ensure xor relationship
    op.create_check_constraint('ck_message_one_parent', 'messages', "((channel_id IS NOT NULL) <> (direct_conversation_id IS NOT NULL))")


def downgrade():
    op.drop_constraint('ck_message_one_parent', 'messages', type_='check')
    op.drop_constraint('fk_messages_direct_conversation', 'messages', type_='foreignkey')
    op.drop_column('messages', 'direct_conversation_id')

    op.drop_table('direct_conversation_participants')
    op.drop_constraint('uq_direct_conversation_pair', 'direct_conversations', type_='unique')
    op.drop_table('direct_conversations')

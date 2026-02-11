"""Add direct_conversation_reads table

Revision ID: 058_add_direct_conversation_reads
Revises: 057_nullable_messages_channel_id
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '058_add_direct_conversation_reads'
down_revision = '057_nullable_messages_channel_id'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'direct_conversation_reads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('direct_conversation_id', sa.Integer(), nullable=False),
        sa.Column('last_read_message_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_direct_reads_conv_message', 'direct_conversation_reads', ['direct_conversation_id', 'last_read_message_id'])


def downgrade():
    op.drop_index('ix_direct_reads_conv_message', table_name='direct_conversation_reads')
    op.drop_table('direct_conversation_reads'
)
"""Add channel_reads table for read receipts

Revision ID: 009_add_channel_reads
Revises: 008
Create Date: 2025-12-24
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '009'
down_revision: Union[str, Sequence[str], None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'channel_reads' not in tables:
        op.create_table(
            'channel_reads',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id'), nullable=False),
            sa.Column('last_read_message_id', sa.Integer(), sa.ForeignKey('messages.id'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        )
        
        # Unique constraint on (user_id, channel_id)
        op.create_unique_constraint(
            'uq_channel_reads_user_channel',
            'channel_reads',
            ['user_id', 'channel_id']
        )
        
        # Index for efficient queries by channel and message
        op.create_index(
            'ix_channel_reads_channel_message',
            'channel_reads',
            ['channel_id', 'last_read_message_id']
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'channel_reads' in tables:
        op.drop_index('ix_channel_reads_channel_message', table_name='channel_reads')
        op.drop_constraint('uq_channel_reads_user_channel', 'channel_reads', type_='unique')
        op.drop_table('channel_reads')

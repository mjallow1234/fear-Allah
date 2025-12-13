"""Add chat-related models (idempotent)

Revision ID: 007_add_chat_models
Revises: 006_normalize_enum_lowercase
Create Date: 2025-12-12
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '007_add_chat_models'
down_revision: Union[str, Sequence[str], None] = '006_normalize_enum_lowercase'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Create notifications table if missing
    if 'notifications' not in tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('type', sa.String(50), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('content', sa.Text()),
            sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id')),
            sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id')),
            sa.Column('sender_id', sa.Integer(), sa.ForeignKey('users.id')),
            sa.Column('is_read', sa.Boolean(), server_default='false'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'notifications' in tables:
        op.drop_table('notifications')

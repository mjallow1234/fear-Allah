"""Add last_read_at and last_viewed_at to channel_members

Revision ID: 008_add_channel_member_read_fields
Revises: 007_add_chat_models
Create Date: 2025-12-18
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '008'
down_revision: Union[str, Sequence[str], None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c['name'] for c in inspector.get_columns('channel_members')}

    if 'last_read_at' not in cols:
        op.add_column('channel_members', sa.Column('last_read_at', sa.DateTime(timezone=True), nullable=True))
    # last_viewed_at is an optional future field
    if 'last_viewed_at' not in cols:
        op.add_column('channel_members', sa.Column('last_viewed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c['name'] for c in inspector.get_columns('channel_members')}

    if 'last_viewed_at' in cols:
        op.drop_column('channel_members', 'last_viewed_at')
    if 'last_read_at' in cols:
        op.drop_column('channel_members', 'last_read_at')

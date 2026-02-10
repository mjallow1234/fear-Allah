"""add legacy dm migrations table

Revision ID: 056_add_legacy_dm_migrations
Revises: 055_add_direct_conversations
Create Date: 2026-02-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '056_add_legacy_dm_migrations'
down_revision = '055_add_direct_conversations'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'legacy_dm_migrations',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('legacy_channel_id', sa.Integer(), nullable=False),
        sa.Column('direct_conversation_id', sa.Integer(), nullable=False),
        sa.Column('message_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('migrated', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('migrated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('legacy_channel_id', name='uq_legacy_dm_channel'),
        sa.UniqueConstraint('direct_conversation_id', name='uq_legacy_dm_direct_conv')
    )


def downgrade():
    op.drop_table('legacy_dm_migrations')

"""allow messages.channel_id to be nullable for direct messages

Revision ID: 057_nullable_messages_channel_id
Revises: 056_add_legacy_dm_migrations
Create Date: 2026-02-11 00:00:00.000000
"""
from alembic import op

import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '057_nullable_messages_channel_id'
down_revision = '056_add_legacy_dm_migrations'
branch_labels = None
depends_on = None


def upgrade():
    """Make messages.channel_id nullable to allow DM messages (direct conversations).

    This corrects a production schema mismatch where the column remained NOT NULL
    after Phase 2 changes introduced direct_conversation_id and the XOR constraint.
    """
    op.alter_column(
        "messages",
        "channel_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    """Revert messages.channel_id to NOT NULL."""
    op.alter_column(
        "messages",
        "channel_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

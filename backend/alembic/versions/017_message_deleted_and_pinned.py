"""
Add deleted_at and is_pinned to messages table

Revision ID: 017_message_deleted_and_pinned
Revises: 016_reaction_unique_constraint
Create Date: 2025-12-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('messages', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade():
    op.drop_column('messages', 'is_pinned')
    op.drop_column('messages', 'deleted_at')

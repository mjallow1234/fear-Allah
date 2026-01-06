"""Add unique constraint to message_reactions

Revision ID: 016
Revises: 015
Create Date: 2025-01-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '016'
down_revision: Union[str, None] = '015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate reactions
    # First, remove any existing duplicates
    op.execute("""
        DELETE FROM message_reactions 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM message_reactions 
            GROUP BY message_id, user_id, emoji
        )
    """)
    
    # Add unique constraint
    op.create_unique_constraint(
        'uq_message_reactions_message_user_emoji',
        'message_reactions',
        ['message_id', 'user_id', 'emoji']
    )
    
    # Add composite index for faster lookups
    op.create_index(
        'ix_message_reactions_message_emoji',
        'message_reactions',
        ['message_id', 'emoji']
    )


def downgrade() -> None:
    op.drop_index('ix_message_reactions_message_emoji', 'message_reactions')
    op.drop_constraint('uq_message_reactions_message_user_emoji', 'message_reactions')

"""Add thread tracking fields to messages

Revision ID: 002_thread_fields
Revises: 002
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_thread_fields'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add thread tracking and edit audit fields to messages table
    op.add_column('messages', sa.Column('thread_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('messages', sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('editor_id', sa.Integer(), nullable=True))
    
    # Add foreign key for editor_id
    op.create_foreign_key(
        'fk_messages_editor_id',
        'messages', 'users',
        ['editor_id'], ['id']
    )
    
    # Update existing messages to have last_activity_at = created_at
    op.execute("UPDATE messages SET last_activity_at = created_at WHERE last_activity_at IS NULL")
    
    # Update thread_count for existing parent messages
    op.execute("""
        UPDATE messages SET thread_count = (
            SELECT COUNT(*) FROM messages AS replies 
            WHERE replies.parent_id = messages.id AND replies.is_deleted = false
        )
        WHERE EXISTS (
            SELECT 1 FROM messages AS replies 
            WHERE replies.parent_id = messages.id
        )
    """)


def downgrade() -> None:
    op.drop_constraint('fk_messages_editor_id', 'messages', type_='foreignkey')
    op.drop_column('messages', 'editor_id')
    op.drop_column('messages', 'edited_at')
    op.drop_column('messages', 'last_activity_at')
    op.drop_column('messages', 'thread_count')

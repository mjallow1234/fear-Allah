"""Enhanced message_attachments table for Phase 9.1

Revision ID: 015_message_attachments_enhanced
Revises: 014_role_permission_enhancements
Create Date: 2025-12-28

Adds:
- uploader_id column (who uploaded the file)
- storage_path column (for local storage path)
- Renames/updates columns for clarity
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '015'
down_revision: Union[str, Sequence[str], None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    # Check if table exists
    if 'file_attachments' in tables:
        columns = [col['name'] for col in inspector.get_columns('file_attachments')]
        
        # Add uploader_id if missing
        if 'uploader_id' not in columns and 'user_id' not in columns:
            op.add_column('file_attachments', 
                sa.Column('uploader_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True)
            )
        
        # Add storage_path if missing (separate from file_path for flexibility)
        if 'storage_path' not in columns:
            op.add_column('file_attachments',
                sa.Column('storage_path', sa.String(500), nullable=True)
            )
        
        # Make message_id nullable (file can exist before being attached to message)
        # This is already nullable in the model, but migration may have different default
        # We'll handle this via model definition
        
        # Add channel_id if missing
        if 'channel_id' not in columns:
            op.add_column('file_attachments',
                sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id'), nullable=True)
            )
    else:
        # Create the table fresh if it doesn't exist
        op.create_table(
            'file_attachments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=True),
            sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id'), nullable=False),
            sa.Column('uploader_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('original_filename', sa.String(255), nullable=False),
            sa.Column('storage_path', sa.String(500), nullable=False),
            sa.Column('file_size', sa.Integer(), nullable=False),
            sa.Column('mime_type', sa.String(100), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        # Add index for efficient lookups
        op.create_index('ix_file_attachments_message_id', 'file_attachments', ['message_id'])
        op.create_index('ix_file_attachments_channel_id', 'file_attachments', ['channel_id'])
        op.create_index('ix_file_attachments_uploader_id', 'file_attachments', ['uploader_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'file_attachments' in tables:
        columns = [col['name'] for col in inspector.get_columns('file_attachments')]
        
        if 'uploader_id' in columns:
            op.drop_column('file_attachments', 'uploader_id')
        if 'storage_path' in columns:
            op.drop_column('file_attachments', 'storage_path')
        if 'channel_id' in columns:
            op.drop_column('file_attachments', 'channel_id')

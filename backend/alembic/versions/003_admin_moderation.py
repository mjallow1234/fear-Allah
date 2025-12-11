"""Add admin moderation fields

Revision ID: 003
Revises: 002_thread_fields
Create Date: 2025-01-03

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002_thread_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add role enum type
    role_enum = sa.Enum('system_admin', 'team_admin', 'member', 'guest', name='userrole')
    role_enum.create(op.get_bind(), checkfirst=True)
    
    # Add user moderation fields
    op.add_column('users', sa.Column('role', sa.Enum('system_admin', 'team_admin', 'member', 'guest', name='userrole'), nullable=True))
    op.add_column('users', sa.Column('is_banned', sa.Boolean(), server_default='false'))
    op.add_column('users', sa.Column('ban_reason', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('banned_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('banned_by_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('is_muted', sa.Boolean(), server_default='false'))
    op.add_column('users', sa.Column('muted_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('muted_reason', sa.String(500), nullable=True))
    
    # Add foreign key for banned_by
    op.create_foreign_key(
        'fk_users_banned_by_id',
        'users', 'users',
        ['banned_by_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Add channel archive fields
    op.add_column('channels', sa.Column('is_archived', sa.Boolean(), server_default='false'))
    op.add_column('channels', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('channels', sa.Column('archived_by_id', sa.Integer(), nullable=True))
    op.add_column('channels', sa.Column('retention_days', sa.Integer(), server_default='0'))
    
    # Add foreign key for archived_by
    op.create_foreign_key(
        'fk_channels_archived_by_id',
        'channels', 'users',
        ['archived_by_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create indexes for faster queries
    op.create_index('ix_users_is_banned', 'users', ['is_banned'])
    op.create_index('ix_users_is_muted', 'users', ['is_muted'])
    op.create_index('ix_users_role', 'users', ['role'])
    op.create_index('ix_channels_is_archived', 'channels', ['is_archived'])
    
    # Set default role for existing users
    op.execute("UPDATE users SET role = 'member' WHERE role IS NULL AND is_system_admin = false")
    op.execute("UPDATE users SET role = 'system_admin' WHERE role IS NULL AND is_system_admin = true")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_channels_is_archived', 'channels')
    op.drop_index('ix_users_role', 'users')
    op.drop_index('ix_users_is_muted', 'users')
    op.drop_index('ix_users_is_banned', 'users')
    
    # Drop foreign keys
    op.drop_constraint('fk_channels_archived_by_id', 'channels', type_='foreignkey')
    op.drop_constraint('fk_users_banned_by_id', 'users', type_='foreignkey')
    
    # Drop channel columns
    op.drop_column('channels', 'retention_days')
    op.drop_column('channels', 'archived_by_id')
    op.drop_column('channels', 'archived_at')
    op.drop_column('channels', 'is_archived')
    
    # Drop user columns
    op.drop_column('users', 'muted_reason')
    op.drop_column('users', 'muted_until')
    op.drop_column('users', 'is_muted')
    op.drop_column('users', 'banned_by_id')
    op.drop_column('users', 'banned_at')
    op.drop_column('users', 'ban_reason')
    op.drop_column('users', 'is_banned')
    op.drop_column('users', 'role')
    
    # Drop enum type
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)

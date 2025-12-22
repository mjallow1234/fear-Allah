"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2025-01-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types used by models
    userstatus_enum = sa.Enum('online', 'away', 'dnd', 'offline', name='userstatus')
    userstatus_enum.create(op.get_bind(), checkfirst=True)
    channeltype_enum = sa.Enum('public', 'private', 'direct', name='channeltype')
    channeltype_enum.create(op.get_bind(), checkfirst=True)
    userrole_enum = sa.Enum('system_admin', 'team_admin', 'member', 'guest', name='userrole')
    userrole_enum.create(op.get_bind(), checkfirst=True)

    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(100)),
        sa.Column('avatar_url', sa.String(500)),
        sa.Column('status', sa.String(20), server_default='offline'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_system_admin', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # Teams table
    op.create_table(
        'teams',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('display_name', sa.String(200)),
        sa.Column('description', sa.Text()),
        sa.Column('icon_url', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # Team members table
    op.create_table(
        'team_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=False),
        sa.Column('role', sa.String(50), server_default='member'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Channels table
    op.create_table(
        'channels',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, index=True),
        sa.Column('display_name', sa.String(200)),
        sa.Column('description', sa.Text()),
        sa.Column('type', sa.String(20), server_default='public'),
        sa.Column('team_id', sa.Integer(), sa.ForeignKey('teams.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # Channel members table
    op.create_table(
        'channel_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id'), nullable=False),
        sa.Column('last_read_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('channel_id', sa.Integer(), sa.ForeignKey('channels.id'), nullable=False),
        sa.Column('author_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('messages.id')),
        sa.Column('is_edited', sa.Boolean(), server_default='false'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    # File attachments table
    op.create_table(
        'file_attachments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer()),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('file_attachments')
    op.drop_table('messages')
    op.drop_table('channel_members')
    op.drop_table('channels')
    op.drop_table('team_members')
    op.drop_table('teams')
    op.drop_table('users')

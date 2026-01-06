"""
Add is_deleted and edited_at columns to messages table if missing

Revision ID: 018_add_is_deleted_and_edited_at
Revises: 017_message_deleted_and_pinned
Create Date: 2025-12-29 00:10:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = None
    try:
        from sqlalchemy import inspect
        insp = inspect(conn)
    except Exception:
        insp = None

    columns = []
    if insp:
        try:
            columns = [c['name'] for c in insp.get_columns('messages')]
        except Exception:
            columns = []

    if 'is_deleted' not in columns:
        op.add_column('messages', sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    if 'edited_at' not in columns:
        op.add_column('messages', sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    conn = op.get_bind()
    insp = None
    try:
        from sqlalchemy import inspect
        insp = inspect(conn)
    except Exception:
        insp = None

    columns = []
    if insp:
        try:
            columns = [c['name'] for c in insp.get_columns('messages')]
        except Exception:
            columns = []

    if 'edited_at' in columns:
        op.drop_column('messages', 'edited_at')
    if 'is_deleted' in columns:
        op.drop_column('messages', 'is_deleted')

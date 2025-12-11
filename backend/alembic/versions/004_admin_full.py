"""Admin & Moderation: roles, audit, indexes

Revision ID: 004
Revises: 003
Create Date: 2025-12-08
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None

def upgrade():
    # Add indexes for users and audit_logs
    # Use idempotent SQL to avoid duplicate-index errors if index already exists
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_is_banned ON users (is_banned)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_is_muted ON users (is_muted)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)")
    # Add metadata column to audit_logs
    # Add metadata column if it doesn't exist
    op.execute("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS meta TEXT")
    # Rename details to meta if details exists
    with op.batch_alter_table('audit_logs') as batch_op:
        # Drop old 'details' column if present
        op.execute("ALTER TABLE audit_logs DROP COLUMN IF EXISTS details")

def downgrade():
    op.drop_index('ix_audit_logs_created_at', 'audit_logs')
    op.drop_index('ix_audit_logs_user_id', 'audit_logs')
    op.drop_index('ix_users_is_muted', 'users')
    op.drop_index('ix_users_is_banned', 'users')
    op.drop_index('ix_users_role', 'users')
    op.drop_column('audit_logs', 'meta')

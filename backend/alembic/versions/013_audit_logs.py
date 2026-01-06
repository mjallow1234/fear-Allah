"""Phase 8.2 - Admin Audit Log Enhancements

Revision ID: 013
Revises: 012_notification_engine
Create Date: 2025-12-28

Adds new columns to audit_logs table for enhanced tracking:
- username (denormalized for display)
- description (human-readable summary)
- request_id (for log correlation)
Also adds indexes for filtering.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to existing audit_logs table
    op.add_column('audit_logs', sa.Column('username', sa.String(100), nullable=True))
    op.add_column('audit_logs', sa.Column('description', sa.String(500), nullable=True))
    op.add_column('audit_logs', sa.Column('request_id', sa.String(50), nullable=True))
    
    # Add indexes for common queries
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_target_type', 'audit_logs', ['target_type'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_target_type', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_column('audit_logs', 'request_id')
    op.drop_column('audit_logs', 'description')
    op.drop_column('audit_logs', 'username')

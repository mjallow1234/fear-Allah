"""merge all remaining alembic heads

Revision ID: 043_merge_all_heads
Revises: 002_thread_fields, 006, 013, 014_add_agent_foreman_userrole, 015, 027, 042_merge_041_and_90fb72034596, add_audit_logs_table, merge_00075132_039
Create Date: 2026-01-28 00:05:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '043_merge_all_heads'
down_revision = (
    '002_thread_fields',
    '006',
    '013',
    '014_add_agent_foreman_userrole',
    '015',
    '027',
    '042_merge_041_and_90fb72034596',
    'add_audit_logs_table',
    'merge_00075132_039',
)
branch_labels = None
depends_on = None


def upgrade():
    # Merge-only revision: no schema changes.
    pass


def downgrade():
    # No-op downgrade for merge revision
    pass

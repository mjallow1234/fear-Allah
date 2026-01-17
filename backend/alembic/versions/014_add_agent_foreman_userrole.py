"""Add agent and foreman to userrole enum

Revision ID: 014_add_agent_foreman_userrole
Revises: 013_add_storekeeper_userrole
Create Date: 2026-01-17

Adds the 'agent' and 'foreman' values to the `userrole` enum in Postgres.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '014_add_agent_foreman_userrole'
down_revision = '013_add_storekeeper_userrole'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'agent';
            ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'foreman';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    # Not reversible in a simple way; leave as no-op
    pass

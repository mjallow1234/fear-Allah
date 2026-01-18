"""Add storekeeper userrole

Revision ID: 013_add_storekeeper_userrole
Revises: 012_notification_engine
Create Date: 2026-01-17

Adds the 'storekeeper' value to the `userrole` enum in Postgres.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '013_add_storekeeper_userrole'
down_revision = '012_notification_engine'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'storekeeper' to the userrole enum if it doesn't exist
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'storekeeper';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    # Note: Postgres does not support removing enum values easily; leave as no-op
    pass

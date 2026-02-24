"""Create notificationtype enum and convert notifications.type to enum

Revision ID: 00c_create_notificationtype_enum
Revises: 011
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '00c_create_notificationtype_enum'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notificationtype enum with baseline + known values (idempotent)
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtype') THEN
            CREATE TYPE notificationtype AS ENUM (
                'mention', 'reply', 'dm', 'dm_message', 'dm_reply', 'channel_reply', 'reaction',
                'task_opened', 'task_claimed', 'task_assigned', 'task_completed', 'task_auto_closed',
                'task_step_completed', 'order_created', 'order_completed', 'low_stock', 'inventory_restocked',
                'sale_recorded', 'system'
            );
        END IF;
    EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # Convert notifications.type column (if exists and not already enum) to the enum type
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'notifications' in inspector.get_table_names():
        cols = {c['name']: c for c in inspector.get_columns('notifications')}
        if 'type' in cols:
            # udt_name will be 'varchar' or 'notificationtype'
            udt_name = cols['type'].get('udt_name')
            if udt_name != 'notificationtype':
                # Safely alter column to enum using text cast (will fail if values incompatible)
                op.execute("ALTER TABLE notifications ALTER COLUMN type TYPE notificationtype USING type::text::notificationtype;")


def downgrade() -> None:
    # We intentionally do not DROP the enum to avoid removing values used elsewhere.
    pass

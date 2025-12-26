"""Phase 6.4 - Notification Engine

Revision ID: 012
Revises: 011
Create Date: 2025-01-09

Adds new notification types for automation events and
new fields for automation context.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_notification_engine'
down_revision = '011_sales_inventory_automation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new notification types to enum
    # First check if we need to add new values to the enum
    op.execute("""
        DO $$ BEGIN
            -- Add new notification types
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'task_assigned';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'task_completed';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'task_auto_closed';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'order_created';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'order_completed';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'low_stock';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'inventory_restocked';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'sale_recorded';
            ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'system';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    # Add new columns to notifications table for automation context
    op.add_column('notifications', sa.Column('task_id', sa.Integer(), nullable=True))
    op.add_column('notifications', sa.Column('order_id', sa.Integer(), nullable=True))
    op.add_column('notifications', sa.Column('inventory_id', sa.Integer(), nullable=True))
    op.add_column('notifications', sa.Column('sale_id', sa.Integer(), nullable=True))
    op.add_column('notifications', sa.Column('extra_data', sa.Text(), nullable=True))
    
    # Add foreign keys
    op.create_foreign_key(
        'fk_notifications_task_id',
        'notifications', 'automation_tasks',
        ['task_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_notifications_order_id',
        'notifications', 'orders',
        ['order_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_notifications_inventory_id',
        'notifications', 'inventory',
        ['inventory_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_notifications_sale_id',
        'notifications', 'sales',
        ['sale_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Add indexes for common queries
    op.create_index('ix_notifications_task_id', 'notifications', ['task_id'])
    op.create_index('ix_notifications_order_id', 'notifications', ['order_id'])
    op.create_index('ix_notifications_inventory_id', 'notifications', ['inventory_id'])
    op.create_index('ix_notifications_sale_id', 'notifications', ['sale_id'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_notifications_sale_id', table_name='notifications')
    op.drop_index('ix_notifications_inventory_id', table_name='notifications')
    op.drop_index('ix_notifications_order_id', table_name='notifications')
    op.drop_index('ix_notifications_task_id', table_name='notifications')
    
    # Remove foreign keys
    op.drop_constraint('fk_notifications_sale_id', 'notifications', type_='foreignkey')
    op.drop_constraint('fk_notifications_inventory_id', 'notifications', type_='foreignkey')
    op.drop_constraint('fk_notifications_order_id', 'notifications', type_='foreignkey')
    op.drop_constraint('fk_notifications_task_id', 'notifications', type_='foreignkey')
    
    # Remove columns
    op.drop_column('notifications', 'extra_data')
    op.drop_column('notifications', 'sale_id')
    op.drop_column('notifications', 'inventory_id')
    op.drop_column('notifications', 'order_id')
    op.drop_column('notifications', 'task_id')
    
    # Note: Enum values cannot be easily removed in PostgreSQL
    # They will remain but be unused

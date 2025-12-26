"""Add sales & inventory automation tables (Phase 6.3)

Revision ID: 011_sales_inventory_automation
Revises: 010_automation_engine
Create Date: 2025-12-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011_sales_inventory_automation'
down_revision = '010_automation_engine'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create inventory_transactions table
    op.create_table(
        'inventory_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('change', sa.Integer(), nullable=False),  # negative for sale, positive for restock
        sa.Column('reason', sa.String(50), nullable=False),  # sale, restock, adjustment
        sa.Column('related_sale_id', sa.Integer(), nullable=True),
        sa.Column('related_order_id', sa.Integer(), nullable=True),
        sa.Column('performed_by_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory.id'], ),
        sa.ForeignKeyConstraint(['related_sale_id'], ['sales.id'], ),
        sa.ForeignKeyConstraint(['related_order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['performed_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inventory_transactions_id', 'inventory_transactions', ['id'])
    op.create_index('ix_inventory_transactions_inventory_item_id', 'inventory_transactions', ['inventory_item_id'])
    op.create_index('ix_inventory_transactions_reason', 'inventory_transactions', ['reason'])
    op.create_index('ix_inventory_transactions_created_at', 'inventory_transactions', ['created_at'])

    # Add location column to sales table
    op.add_column('sales', sa.Column('location', sa.String(255), nullable=True))

    # Add low_stock_threshold column to inventory table
    op.add_column('inventory', sa.Column('low_stock_threshold', sa.Integer(), server_default='10', nullable=False))
    
    # Add product_name column to inventory table for display
    op.add_column('inventory', sa.Column('product_name', sa.String(255), nullable=True))


def downgrade() -> None:
    # Drop columns
    op.drop_column('inventory', 'product_name')
    op.drop_column('inventory', 'low_stock_threshold')
    op.drop_column('sales', 'location')
    
    # Drop table
    op.drop_table('inventory_transactions')


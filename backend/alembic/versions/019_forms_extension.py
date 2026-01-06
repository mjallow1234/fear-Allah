"""Forms Extension - Order, Sale, RawMaterial enhancements

Revision ID: 019_forms_extension
Revises: 018_add_is_deleted_and_edited_at
Create Date: 2026-01-04

Adds optional fields to Order and Sale models.
Creates RawMaterial model for inventory management.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # =========================================
    # ORDER MODEL EXTENSIONS
    # =========================================
    op.add_column('orders', sa.Column('reference', sa.String(100), nullable=True))
    op.add_column('orders', sa.Column('priority', sa.String(20), nullable=True))  # low, normal, high, urgent
    op.add_column('orders', sa.Column('requested_delivery_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('orders', sa.Column('customer_name', sa.String(200), nullable=True))
    op.add_column('orders', sa.Column('customer_phone', sa.String(50), nullable=True))
    op.add_column('orders', sa.Column('payment_method', sa.String(50), nullable=True))  # cash, card, transfer, credit
    op.add_column('orders', sa.Column('internal_comment', sa.Text(), nullable=True))
    
    # =========================================
    # SALE MODEL EXTENSIONS
    # =========================================
    op.add_column('sales', sa.Column('reference', sa.String(100), nullable=True))
    op.add_column('sales', sa.Column('customer_name', sa.String(200), nullable=True))
    op.add_column('sales', sa.Column('customer_phone', sa.String(50), nullable=True))
    op.add_column('sales', sa.Column('discount', sa.Integer(), nullable=True))  # Discount in currency units
    op.add_column('sales', sa.Column('payment_method', sa.String(50), nullable=True))
    op.add_column('sales', sa.Column('sale_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sales', sa.Column('linked_order_id', sa.Integer(), nullable=True))
    # Affiliate fields
    op.add_column('sales', sa.Column('affiliate_code', sa.String(100), nullable=True))
    op.add_column('sales', sa.Column('affiliate_name', sa.String(200), nullable=True))
    op.add_column('sales', sa.Column('affiliate_source', sa.String(50), nullable=True))  # web, whatsapp, referral, unknown
    
    # Add foreign key for linked_order_id
    op.create_foreign_key(
        'fk_sales_linked_order_id',
        'sales', 'orders',
        ['linked_order_id'], ['id']
    )
    
    # =========================================
    # RAW MATERIAL MODEL (NEW)
    # =========================================
    op.create_table(
        'raw_materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('unit', sa.String(50), nullable=False),  # kg, liters, pieces, etc.
        sa.Column('current_stock', sa.Integer(), default=0, nullable=False),
        sa.Column('min_stock_level', sa.Integer(), default=0, nullable=True),
        sa.Column('cost_per_unit', sa.Integer(), nullable=True),  # Cost in smallest currency unit
        sa.Column('supplier', sa.String(255), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_raw_materials_id', 'raw_materials', ['id'])
    op.create_index('ix_raw_materials_name', 'raw_materials', ['name'])
    
    # Raw material transactions (audit log)
    op.create_table(
        'raw_material_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('raw_material_id', sa.Integer(), nullable=False),
        sa.Column('change', sa.Integer(), nullable=False),  # positive for add, negative for consume
        sa.Column('reason', sa.String(50), nullable=False),  # add, consume, adjust, return
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('performed_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['raw_material_id'], ['raw_materials.id']),
        sa.ForeignKeyConstraint(['performed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_raw_material_transactions_id', 'raw_material_transactions', ['id'])
    op.create_index('ix_raw_material_transactions_raw_material_id', 'raw_material_transactions', ['raw_material_id'])


def downgrade() -> None:
    # Drop raw material tables
    op.drop_table('raw_material_transactions')
    op.drop_table('raw_materials')
    
    # Drop sales extensions
    op.drop_constraint('fk_sales_linked_order_id', 'sales', type_='foreignkey')
    op.drop_column('sales', 'affiliate_source')
    op.drop_column('sales', 'affiliate_name')
    op.drop_column('sales', 'affiliate_code')
    op.drop_column('sales', 'linked_order_id')
    op.drop_column('sales', 'sale_date')
    op.drop_column('sales', 'payment_method')
    op.drop_column('sales', 'discount')
    op.drop_column('sales', 'customer_phone')
    op.drop_column('sales', 'customer_name')
    op.drop_column('sales', 'reference')
    
    # Drop orders extensions
    op.drop_column('orders', 'internal_comment')
    op.drop_column('orders', 'payment_method')
    op.drop_column('orders', 'customer_phone')
    op.drop_column('orders', 'customer_name')
    op.drop_column('orders', 'requested_delivery_date')
    op.drop_column('orders', 'priority')
    op.drop_column('orders', 'reference')

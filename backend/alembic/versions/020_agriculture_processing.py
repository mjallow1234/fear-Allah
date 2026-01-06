"""Agriculture processing - product types and recipes

Revision ID: 020_agriculture_processing
Revises: 019_forms_extension
Create Date: 2026-01-05

Adds:
- ProductType enum (RAW_MATERIAL, FINISHED_GOOD, TRADE_GOOD)
- product_type column to inventory table
- processing_recipes table for finished good recipes
- processing_batches table for manufacturing runs
- related_batch_id to inventory_transactions and raw_material_transactions
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ProductType enum
    op.execute("CREATE TYPE producttype AS ENUM ('RAW_MATERIAL', 'FINISHED_GOOD', 'TRADE_GOOD')")
    
    # Add product_type to inventory table with default
    op.add_column('inventory', sa.Column('product_type', 
        sa.Enum('RAW_MATERIAL', 'FINISHED_GOOD', 'TRADE_GOOD', name='producttype', create_type=False),
        nullable=False, server_default='TRADE_GOOD'))
    
    # Create processing_batches table first (needed for FK)
    op.create_table('processing_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_reference', sa.String(length=100), nullable=True),
        sa.Column('finished_product_id', sa.Integer(), nullable=False),
        sa.Column('quantity_produced', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='completed'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('processed_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['finished_product_id'], ['inventory.id'], ),
        sa.ForeignKeyConstraint(['processed_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('batch_reference')
    )
    op.create_index('ix_processing_batches_finished_product_id', 'processing_batches', ['finished_product_id'])
    op.create_index('ix_processing_batches_status', 'processing_batches', ['status'])
    op.create_index('ix_processing_batches_created_at', 'processing_batches', ['created_at'])
    
    # Create processing_recipes table
    op.create_table('processing_recipes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('finished_product_id', sa.Integer(), nullable=False),
        sa.Column('raw_material_id', sa.Integer(), nullable=False),
        sa.Column('quantity_required', sa.Integer(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('waste_percentage', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['finished_product_id'], ['inventory.id'], ),
        sa.ForeignKeyConstraint(['raw_material_id'], ['raw_materials.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('finished_product_id', 'raw_material_id', name='uq_recipe_product_material')
    )
    op.create_index('ix_processing_recipes_finished_product_id', 'processing_recipes', ['finished_product_id'])
    
    # Add related_batch_id to inventory_transactions
    op.add_column('inventory_transactions', 
        sa.Column('related_batch_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_inventory_transactions_batch', 
        'inventory_transactions', 'processing_batches', 
        ['related_batch_id'], ['id'])
    
    # Add related_batch_id to raw_material_transactions
    op.add_column('raw_material_transactions', 
        sa.Column('related_batch_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_raw_material_transactions_batch', 
        'raw_material_transactions', 'processing_batches', 
        ['related_batch_id'], ['id'])


def downgrade() -> None:
    # Drop foreign keys first
    op.drop_constraint('fk_raw_material_transactions_batch', 'raw_material_transactions', type_='foreignkey')
    op.drop_column('raw_material_transactions', 'related_batch_id')
    
    op.drop_constraint('fk_inventory_transactions_batch', 'inventory_transactions', type_='foreignkey')
    op.drop_column('inventory_transactions', 'related_batch_id')
    
    # Drop tables
    op.drop_index('ix_processing_recipes_finished_product_id', table_name='processing_recipes')
    op.drop_table('processing_recipes')
    
    op.drop_index('ix_processing_batches_created_at', table_name='processing_batches')
    op.drop_index('ix_processing_batches_status', table_name='processing_batches')
    op.drop_index('ix_processing_batches_finished_product_id', table_name='processing_batches')
    op.drop_table('processing_batches')
    
    # Drop product_type column and enum
    op.drop_column('inventory', 'product_type')
    op.execute("DROP TYPE producttype")

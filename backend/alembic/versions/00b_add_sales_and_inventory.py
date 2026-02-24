"""Create sales and inventory base tables

Revision ID: 00b_add_sales_and_inventory
Revises: 010
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '00b_add_sales_and_inventory'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create salechannel enum (idempotent)
    op.execute("DO $$ BEGIN CREATE TYPE salechannel AS ENUM ('field','store','delivery','direct'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # Create sales table (base columns only; later migrations add extensions)
    op.create_table(
        'sales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Integer(), nullable=False),
        sa.Column('total_amount', sa.Integer(), nullable=False),
        sa.Column('sold_by_user_id', sa.Integer(), nullable=False),
        sa.Column('sale_channel', postgresql.ENUM(name='salechannel', create_type=False), nullable=False),
        sa.Column('related_order_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['sold_by_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_sales_id', 'sales', ['id'])
    op.create_index('ix_sales_product_id', 'sales', ['product_id'])

    # Create inventory table (base columns; extended columns added by later migrations)
    op.create_table(
        'inventory',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False, unique=True),
        sa.Column('total_stock', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_sold', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('low_stock_threshold', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_inventory_id', 'inventory', ['id'])
    op.create_index('ix_inventory_product_id', 'inventory', ['product_id'])


def downgrade() -> None:
    op.drop_index('ix_inventory_product_id', table_name='inventory')
    op.drop_index('ix_inventory_id', table_name='inventory')
    op.drop_table('inventory')

    op.drop_index('ix_sales_product_id', table_name='sales')
    op.drop_index('ix_sales_id', table_name='sales')
    op.drop_table('sales')

    op.execute("DROP TYPE IF EXISTS salechannel")

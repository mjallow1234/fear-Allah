"""Core commerce tables (sales & inventory)

Revision ID: 010a
Revises: 010
Create Date: 2026-01-06
"""
from alembic import op
import sqlalchemy as sa

revision = '010a'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Inventory table
    op.create_table(
        'inventory',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sku', sa.String(100), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True))
    )

    # Sales table
    op.create_table(
        'sales',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'])
    )


def downgrade() -> None:
    op.drop_table('sales')
    op.drop_table('inventory')

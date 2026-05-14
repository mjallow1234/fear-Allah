"""Add sale reversal columns to sales table

Revision ID: 091_add_sale_reversal_columns
Revises: 090_add_last_activity_indexes
Create Date: 2026-04-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '091_add_sale_reversal_columns'
down_revision = '090_add_last_activity_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales', sa.Column('is_reversed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sales', sa.Column('reversed_by_id', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('reversed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_sales_reversed_by_id_users',
        'sales', 'users', ['reversed_by_id'], ['id']
    )


def downgrade():
    op.drop_constraint('fk_sales_reversed_by_id_users', 'sales', type_='foreignkey')
    op.drop_column('sales', 'reversed_at')
    op.drop_column('sales', 'reversed_by_id')
    op.drop_column('sales', 'is_reversed')

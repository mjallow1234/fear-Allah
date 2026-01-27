"""add channel_id to orders

Revision ID: 040_add_channel_id_to_orders
Revises: 039_add_created_by_to_orders
Create Date: 2026-01-27 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '040_add_channel_id_to_orders'
down_revision = '039_add_created_by_to_orders'
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable channel_id column to orders
    op.add_column('orders', sa.Column('channel_id', sa.Integer(), nullable=True))
    # Create foreign key constraint to channels(id)
    op.create_foreign_key('fk_orders_channel', 'orders', 'channels', ['channel_id'], ['id'])
    # Create index for faster lookups by channel
    op.create_index(op.f('ix_orders_channel_id'), 'orders', ['channel_id'], unique=False)


def downgrade():
    # Drop index, fk, then column
    op.drop_index(op.f('ix_orders_channel_id'), table_name='orders')
    op.drop_constraint('fk_orders_channel', 'orders', type_='foreignkey')
    op.drop_column('orders', 'channel_id')

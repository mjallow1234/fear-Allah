"""add created_by_id to orders

Revision ID: 039_add_created_by_to_orders
Revises: 038_make_task_assignment_user_nullable
Create Date: 2026-01-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '039_add_created_by_to_orders'
down_revision = '038_make_task_assignment_user_nullable'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orders', sa.Column('created_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_orders_created_by', 'orders', 'users', ['created_by_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_orders_created_by', 'orders', type_='foreignkey')
    op.drop_column('orders', 'created_by_id')

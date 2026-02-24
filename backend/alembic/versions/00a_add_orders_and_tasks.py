"""Create orders and tasks base tables

Revision ID: 00a_add_orders_and_tasks
Revises: f93a4f97e6d0
Create Date: 2026-02-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '00a_add_orders_and_tasks'
down_revision = 'f93a4f97e6d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (idempotent)
    op.execute("DO $$ BEGIN CREATE TYPE ordertype AS ENUM ('agent_restock', 'agent_retail', 'store_keeper_restock', 'customer_wholesale'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE orderstatus AS ENUM ('draft','submitted','in_progress','awaiting_confirmation','completed','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE taskstatus AS ENUM ('pending','active','done'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # Create orders table (base columns only; later migrations add extensions)
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_type', postgresql.ENUM(name='ordertype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM(name='orderstatus', create_type=False), nullable=False, server_default='submitted'),
        sa.Column('meta', sa.Text(), nullable=True),
        sa.Column('items', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_orders_id', 'orders', ['id'])
    op.create_index('ix_orders_created_at', 'orders', ['created_at'])

    # Create order workflow tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('step_key', sa.String(100), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('assigned_user_id', sa.Integer(), nullable=True),
        sa.Column('status', postgresql.ENUM(name='taskstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('required', sa.Boolean(), server_default='true'),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tasks_id', 'tasks', ['id'])
    op.create_index('ix_tasks_order_id', 'tasks', ['order_id'])


def downgrade() -> None:
    op.drop_index('ix_tasks_order_id', table_name='tasks')
    op.drop_index('ix_tasks_id', table_name='tasks')
    op.drop_table('tasks')

    op.drop_index('ix_orders_created_at', table_name='orders')
    op.drop_index('ix_orders_id', table_name='orders')
    op.drop_table('orders')

    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS ordertype")

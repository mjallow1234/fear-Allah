"""add user_operational_roles table

Revision ID: 041_add_user_operational_roles
Revises: 040_add_channel_id_to_orders
Create Date: 2026-01-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '041_add_user_operational_roles'
down_revision = '040_add_channel_id_to_orders'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_operational_roles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.UniqueConstraint('user_id', 'role', name='uq_user_operational_role'),
    )
    op.create_index(op.f('ix_user_operational_roles_user_id'), 'user_operational_roles', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_user_operational_roles_user_id'), table_name='user_operational_roles')
    op.drop_table('user_operational_roles')

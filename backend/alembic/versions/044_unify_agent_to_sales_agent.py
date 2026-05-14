"""Unify agent role to sales_agent in user_operational_roles

Revision ID: 044_unify_agent_to_sales_agent
Revises: merge_00075132_039
Create Date: 2026-05-04 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '044_unify_agent_to_sales_agent'
down_revision = 'merge_00075132_039'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE user_operational_roles
        SET role = 'sales_agent'
        WHERE role = 'agent'
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE user_operational_roles
        SET role = 'agent'
        WHERE role = 'sales_agent'
        """
    )

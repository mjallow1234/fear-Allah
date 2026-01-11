"""Add system_state table to persist setup_completed flag

Revision ID: 028_add_system_state
Revises: 027_ai_governance_tags
Create Date: 2026-01-11
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '028_add_system_state'
down_revision: Union[str, Sequence[str], None] = '027_ai_governance_tags'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_state',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('setup_completed', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table('system_state')

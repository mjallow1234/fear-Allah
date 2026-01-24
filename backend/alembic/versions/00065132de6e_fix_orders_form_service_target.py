"""fix orders form service_target

Revision ID: 00065132de6e
Revises: 00055132de5d
Create Date: 2026-01-24 21:40:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00065132de6e"
down_revision: Union[str, Sequence[str], None] = "00055132de5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure the orders form routes to the 'orders' handler, not 'orders.create_order'
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE forms SET service_target = 'orders' WHERE slug = 'orders' AND service_target != 'orders'"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE forms SET service_target = 'orders.create_order' WHERE slug = 'orders' AND service_target = 'orders'"))

"""merge heads after channel_id migration

Revision ID: 90fb72034596
Revises: merge_00075132_039, 040_add_channel_id_to_orders
Create Date: 2026-01-27 19:58:13.125113
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90fb72034596'
down_revision: Union[str, None] = ('merge_00075132_039', '040_add_channel_id_to_orders')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

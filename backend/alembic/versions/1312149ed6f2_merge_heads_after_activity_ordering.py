"""merge heads after activity ordering

Revision ID: 1312149ed6f2
Revises: 090_add_last_activity_indexes, 20ed217e3850
Create Date: 2026-02-13 16:10:05.087736
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1312149ed6f2'
down_revision: Union[str, None] = ('090_add_last_activity_indexes', '20ed217e3850')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

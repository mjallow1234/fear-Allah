"""final merge after duplicate merge heads

Revision ID: b969f87af073
Revises: 47b09ee6de71, 042_merge_041_and_90fb72034596
Create Date: 2026-01-28 12:14:33.446953
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b969f87af073'
down_revision: Union[str, None] = ('47b09ee6de71', '042_merge_041_and_90fb72034596')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

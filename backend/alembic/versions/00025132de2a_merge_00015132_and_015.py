"""merge 00015132de1d and 015

Revision ID: 00025132de2a
Revises: 00015132de1d, 015
Create Date: 2026-01-24 20:50:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00025132de2a"
down_revision: Union[str, Sequence[str], None] = ("00015132de1d", "015")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

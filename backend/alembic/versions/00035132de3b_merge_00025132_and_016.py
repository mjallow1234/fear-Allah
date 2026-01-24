"""merge 00025132de2a and 016

Revision ID: 00035132de3b
Revises: 00025132de2a, 016
Create Date: 2026-01-24 21:10:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00035132de3b"
down_revision: Union[str, Sequence[str], None] = ("00025132de2a", "016")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

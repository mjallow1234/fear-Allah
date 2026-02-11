"""merge dm reads with legacy branch

Revision ID: fe6b12b94ecc
Revises: 058_add_direct_conversation_reads, b969f87af073
Create Date: 2026-02-11 15:44:07.784611
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe6b12b94ecc'
down_revision: Union[str, None] = ('058_add_direct_conversation_reads', 'b969f87af073')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

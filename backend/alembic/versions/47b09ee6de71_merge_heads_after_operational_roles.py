"""merge heads after operational roles

Revision ID: 47b09ee6de71
Revises: 041_add_user_operational_roles, 90fb72034596
Create Date: 2026-01-28 12:03:17.156905
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47b09ee6de71'
down_revision: Union[str, None] = ('041_add_user_operational_roles', '90fb72034596')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

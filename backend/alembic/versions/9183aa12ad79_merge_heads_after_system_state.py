"""merge heads after system_state

Revision ID: 9183aa12ad79
Revises: 009a, 010a, 027, 028_add_system_state
Create Date: 2026-01-12 09:17:39.595881

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9183aa12ad79'
down_revision: Union[str, None] = ('009a', '010a', '027', '028_add_system_state')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

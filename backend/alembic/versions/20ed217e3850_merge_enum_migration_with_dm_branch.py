"""merge enum migration with dm branch

Revision ID: 20ed217e3850
Revises: 059_add_chat_notification_enum_values, fe6b12b94ecc
Create Date: 2026-02-11 17:50:54.373622
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20ed217e3850'
down_revision: Union[str, None] = ('059_add_chat_notification_enum_values', 'fe6b12b94ecc')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

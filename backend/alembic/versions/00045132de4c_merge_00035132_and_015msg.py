"""merge 00035132de3b and 015_message_attachments_enhanced

Revision ID: 00045132de4c
Revises: 00035132de3b, 015_message_attachments_enhanced
Create Date: 2026-01-24 21:15:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00045132de4c"
down_revision: Union[str, Sequence[str], None] = ("00035132de3b", "015_message_attachments_enhanced")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

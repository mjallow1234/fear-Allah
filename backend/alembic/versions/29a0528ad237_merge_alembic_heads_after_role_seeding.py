"""merge alembic heads after role seeding

Revision ID: 29a0528ad237
Revises: 014_add_agent_foreman_userrole, 027
Create Date: 2026-01-18 21:21:38.792739

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29a0528ad237'
down_revision: Union[str, None] = ('014_add_agent_foreman_userrole', '027')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

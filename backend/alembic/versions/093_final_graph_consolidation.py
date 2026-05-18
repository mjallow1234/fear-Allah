"""Final graph consolidation — merge 092, 1312149ed6f2, and b969f87af073.

These three heads represent divergent branches that existed in the VPS
container image but were missing from the git repository.  All three
branches are pure merge no-ops (no DDL); this migration absorbs them into
one canonical head so that both local and VPS share a single, identical
alembic graph going forward.

No schema changes are made here.  This is a graph-only merge.

Revision ID: 093_final_graph_consolidation
Revises:
    092_merge_all_heads
    1312149ed6f2
    b969f87af073
Create Date: 2026-05-18 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = '093_final_graph_consolidation'
down_revision: Union[str, Sequence[str], None] = (
    '092_merge_all_heads',
    '1312149ed6f2',
    'b969f87af073',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Graph-only merge.  All schema corrections were applied in 092.
    pass


def downgrade() -> None:
    pass

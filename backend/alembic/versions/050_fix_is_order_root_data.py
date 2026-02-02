"""fix is_order_root data and ensure exactly one root per order

Revision ID: 050_fix_is_order_root_data
Revises: 049_add_is_order_root_to_automation_tasks
Create Date: 2026-02-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "050_fix_is_order_root_data"
down_revision = "049_add_is_order_root_to_automation_tasks"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Set is_order_root = FALSE for any role-scoped automation tasks
    op.execute("UPDATE automation_tasks SET is_order_root = FALSE WHERE required_role IS NOT NULL;")

    if bind.dialect.name == "postgresql":
        # For orders with multiple roots, keep the earliest (by id) and clear others
        op.execute("""
        WITH ranked AS (
            SELECT id, related_order_id,
                   ROW_NUMBER() OVER (PARTITION BY related_order_id ORDER BY id) AS rn
            FROM automation_tasks
            WHERE related_order_id IS NOT NULL AND is_order_root = TRUE
        )
        UPDATE automation_tasks
        SET is_order_root = FALSE
        FROM ranked
        WHERE automation_tasks.id = ranked.id AND ranked.rn > 1;
        """)

        # For orders with no root, promote the earliest task to be the root
        op.execute("""
        WITH earliest AS (
            SELECT related_order_id, MIN(id) AS min_id
            FROM automation_tasks
            WHERE related_order_id IS NOT NULL
            GROUP BY related_order_id
            HAVING SUM(CASE WHEN is_order_root THEN 1 ELSE 0 END) = 0
        )
        UPDATE automation_tasks
        SET is_order_root = TRUE
        FROM earliest
        WHERE automation_tasks.id = earliest.min_id;
        """)

        # Ensure partial unique index exists
        op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_order_root_per_order ON automation_tasks (related_order_id) WHERE is_order_root = true;")
    else:
        # Best-effort for non-Postgres dialects (e.g., sqlite in tests)
        # Ensure no role-scoped tasks are marked as order root
        op.execute("UPDATE automation_tasks SET is_order_root = 0 WHERE required_role IS NOT NULL;")


def downgrade():
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS uq_order_root_per_order;")

    # Note: We intentionally do not attempt to revert data promotions (non-destructive)

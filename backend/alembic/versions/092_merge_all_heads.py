"""Merge all 6 open heads into a single authoritative head.

Also applies two minimal corrective fixes that are safe to run on both
local and VPS.  Every DDL operation is existence-guarded so this
migration is fully idempotent — running it twice produces no error and
no duplicate objects.

Corrective fixes included:
  1. sales.reversed_at  — cast from TIMESTAMP WITHOUT TIME ZONE to
                          TIMESTAMPTZ (only if not already TIMESTAMPTZ).
                          VPS already has TIMESTAMPTZ so this is a no-op
                          there.  Local dev is missing the timezone spec.
                          Stored values are interpreted as UTC during
                          the USING cast.

  2. fk_sales_reversed_by_id_users — adds the FK from sales.reversed_by_id
                                      to users.id if no FK already covers
                                      that column.  VPS has an equivalent
                                      FK (named sales_reversed_by_id_fkey)
                                      that was created by the manual hotfix;
                                      the existence check matches on column
                                      membership, not constraint name, so
                                      the VPS FK will be detected and this
                                      step will be skipped there.

Revision ID: 092_merge_all_heads
Revises:
    00a_add_orders_and_tasks
    00b_add_sales_and_inventory
    00c_create_notificationtype_enum
    044_unify_agent_to_sales_agent
    091_add_sale_reversal_columns
    fe6b12b94ecc
Create Date: 2026-05-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = '092_merge_all_heads'
down_revision: Union[str, Sequence[str], None] = (
    '00a_add_orders_and_tasks',
    '00b_add_sales_and_inventory',
    '00c_create_notificationtype_enum',
    '044_unify_agent_to_sales_agent',
    '091_add_sale_reversal_columns',
    'fe6b12b94ecc',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# SQL helpers — both blocks are PL/pgSQL DO statements so they execute as
# a single command inside the migration transaction and are inherently
# idempotent via the IF / IF NOT EXISTS guards.
# ---------------------------------------------------------------------------

# Fix 1 — cast sales.reversed_at to TIMESTAMPTZ if it is still plain TIMESTAMP.
# The information_schema lookup returns 'timestamp without time zone' for a
# plain TIMESTAMP column and 'timestamp with time zone' for TIMESTAMPTZ.
# The USING clause interprets existing naïve values as UTC, which is correct
# because all timestamps in this codebase are stored in UTC.
_FIX_REVERSED_AT_TZ = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM   information_schema.columns
        WHERE  table_schema = 'public'
          AND  table_name   = 'sales'
          AND  column_name  = 'reversed_at'
          AND  data_type    = 'timestamp without time zone'
    ) THEN
        ALTER TABLE sales
            ALTER COLUMN reversed_at
            TYPE TIMESTAMP WITH TIME ZONE
            USING reversed_at AT TIME ZONE 'UTC';
    END IF;
END $$;
"""

# Fix 2 — add FK from sales.reversed_by_id -> users.id if no FK already
# covers that column.  The check inspects pg_constraint.conkey (array of
# attribute numbers) to detect any existing FK on the column regardless of
# what that constraint is named.  This means the VPS constraint
# 'sales_reversed_by_id_fkey' (created by the manual hotfix) will be found
# and the ALTER TABLE will be skipped.
_FIX_REVERSED_BY_FK = """
DO $$
DECLARE
    _col_num smallint;
BEGIN
    -- Resolve the attnum of reversed_by_id in the sales table.
    SELECT attnum
      INTO _col_num
      FROM pg_attribute
     WHERE attrelid = 'sales'::regclass
       AND attname  = 'reversed_by_id'
       AND attnum   > 0;

    -- Only create the FK if no foreign-key constraint already includes
    -- reversed_by_id in its column list.
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'sales'::regclass
           AND contype  = 'f'
           AND _col_num = ANY(conkey)
    ) THEN
        ALTER TABLE sales
            ADD CONSTRAINT fk_sales_reversed_by_id_users
            FOREIGN KEY (reversed_by_id)
            REFERENCES users(id);
    END IF;
END $$;
"""


def upgrade() -> None:
    # --- merge only (no DDL) when running on a fully up-to-date schema ------
    # The two op.execute() calls below are self-guarded no-ops on VPS because:
    #   • VPS.reversed_at   is already TIMESTAMPTZ  → Fix 1 IF branch = false
    #   • VPS already has a FK on reversed_by_id    → Fix 2 IF branch = false

    # Fix 1: ensure reversed_at is TIMESTAMPTZ
    op.execute(_FIX_REVERSED_AT_TZ)

    # Fix 2: ensure FK from reversed_by_id to users exists
    op.execute(_FIX_REVERSED_BY_FK)


def downgrade() -> None:
    # Downgrade is intentionally a no-op.
    #
    # Reversing the timezone cast is lossy (UTC offset information cannot be
    # reconstructed) and the FK guard means we cannot know whether this
    # migration created the FK or whether it already existed.  Attempting to
    # drop a constraint that was created by the manual VPS hotfix would be
    # destructive.
    #
    # To undo: stamp the DB back to 091_add_sale_reversal_columns and handle
    # any schema adjustments manually with full knowledge of the environment.
    pass

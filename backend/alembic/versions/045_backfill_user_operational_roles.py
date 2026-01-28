"""backfill user operational roles and normalize users.role

Revision ID: 045_backfill_user_operational_roles
Revises: 044_merge_043_and_b969f87af073
Create Date: 2026-01-28 00:20:00.000000
"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '045_backfill_user_operational_roles'
down_revision = '044_merge_043_and_b969f87af073'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name

    # Backfill operational roles for users whose role is not a system role or 'member'.
    # Use dialect-appropriate upsert/ignore semantics so this is idempotent and ENUM-safe.
    if dialect == 'postgresql':
        conn.execute(text(
            """
            -- Backfill operational roles (idempotent)
            INSERT INTO user_operational_roles (user_id, role)
            SELECT id, role::text
            FROM users
            WHERE role::text NOT IN ('member', 'system_admin', 'team_admin')
            ON CONFLICT (user_id, role) DO NOTHING
            """
        ))
    else:
        # SQLite and others: rely on INSERT OR IGNORE which respects unique constraint
        conn.execute(text(
            """
            INSERT OR IGNORE INTO user_operational_roles (user_id, role)
            SELECT id, role FROM users WHERE role NOT IN ('member', 'system_admin', 'team_admin')
            """
        ))

    # Normalize users.role to 'member' for non-system roles (idempotent)
    if dialect == 'postgresql':
        conn.execute(text("""
            UPDATE users
            SET role = 'member'
            WHERE role::text NOT IN ('member', 'system_admin', 'team_admin')
        """))
    else:
        conn.execute(text("""
            UPDATE users
            SET role = 'member'
            WHERE role NOT IN ('member', 'system_admin', 'team_admin')
        """))


def downgrade():
    # This migration performs data normalization and is not reversed.
    # Downgrade is a no-op; documented as irreversible.
    pass

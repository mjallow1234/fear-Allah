"""add system user (id=0) for automation FK integrity

Revision ID: 048_add_system_user_id_0
Revises: 047_add_task_claimed_notification_type
Create Date: 2026-01-29 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "048_add_system_user_id_0"
down_revision = "047_add_task_claimed_notification_type"
branch_labels = None
depends_on = None


def upgrade():
    """Insert a system user with id=0 to satisfy automation_tasks.created_by_id FK.

    - PostgreSQL-only (skipped on other dialects like SQLite used in tests)
    - Idempotent via `ON CONFLICT DO NOTHING`

    Note: We intentionally keep the inserted row minimal and non-destructive.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # Non-Postgres dialects do not need this change and may have different constraints.
        return

    # Insert a system user (id=0) to represent the system as a task creator.
    # Use ON CONFLICT DO NOTHING so this is safe to run multiple times and in different environments.
    # System user required for automation_tasks.created_by_id FK integrity.
    op.execute("""
    INSERT INTO users (
        id,
        username,
        display_name,
        email,
        hashed_password,
        status,
        role,
        is_active,
        is_system_admin,
        created_at,
        updated_at
    )
    VALUES (
        0,
        'system',
        'System',
        'system@localhost',
        '',
        'offline',        -- users.status enum (use 'offline' since 'active' is not in enum)
        'system_admin',   -- users.role enum
        TRUE,
        TRUE,
        now(),
        now()
    )
    ON CONFLICT DO NOTHING;
    """)


def downgrade():
    """Remove the system user inserted by `upgrade` (Postgres-only).
    Removing the row is safe in downgrade but by default we keep this as a reversible action.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("""
    DELETE FROM users WHERE id = 0;
    """)

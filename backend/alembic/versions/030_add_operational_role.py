"""add operational_role to users

Revision ID: 030_add_operational_role
Revises: 029_normalize_teams_keep_sidrah_salaam
Create Date: 2026-01-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, text

# revision identifiers, used by Alembic.
revision = '030_add_operational_role'
down_revision = '029_normalize_teams_keep_sidrah_salaam'
branch_labels = None
depends_on = None


def upgrade():
    # Create new enum type for operational roles
    oper_enum = sa.Enum('agent', 'foreman', 'delivery', 'storekeeper', name='operationalrole')
    oper_enum.create(op.get_bind(), checkfirst=True)

    # Add column as nullable initially
    op.add_column('users', sa.Column('operational_role', oper_enum, nullable=True))
    op.create_index('ix_users_operational_role', 'users', ['operational_role'])

    # Backfill based on username prefixes and system admin fallback
    # Default unmatched users to 'agent' to keep system operational and avoid blocking migrations.
    op.execute(text("""
        UPDATE users
        SET operational_role = (
            CASE
                WHEN lower(username) LIKE 'agent%' THEN 'agent'::operationalrole
                WHEN lower(username) LIKE 'foreman%' THEN 'foreman'::operationalrole
                WHEN lower(username) LIKE 'delivery%' THEN 'delivery'::operationalrole
                WHEN lower(username) LIKE 'store%' THEN 'storekeeper'::operationalrole
                WHEN is_system_admin = true THEN 'agent'::operationalrole
                ELSE 'agent'::operationalrole
            END
        )
        WHERE operational_role IS NULL
    """))

    # Verify backfill succeeded (no NULLs remain)
    conn = op.get_bind()
    nulls = conn.execute(text("SELECT COUNT(1) FROM users WHERE operational_role IS NULL")).scalar()
    if nulls and int(nulls) > 0:
        raise RuntimeError(f"Migration 030 failed: {int(nulls)} users have NULL operational_role. Please set operational roles manually before applying this migration.")

    # Make column non-nullable
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('operational_role', existing_type=oper_enum, nullable=False)


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_index('ix_users_operational_role')
        batch_op.drop_column('operational_role')

    sa.Enum(name='operationalrole').drop(op.get_bind(), checkfirst=True)

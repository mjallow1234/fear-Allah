"""Add claimable task fields and OPEN/CLAIMED statuses for automation tasks

Revision ID: 036_claimable_tasks
Revises: 035_make_operational_role_nullable
Create Date: 2026-01-23
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '036_claimable_tasks'
down_revision = '035_make_operational_role_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum values safely (no-op if already present)
    op.execute("DO $$ BEGIN ALTER TYPE automationtaskstatus ADD VALUE 'OPEN'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN ALTER TYPE automationtaskstatus ADD VALUE 'CLAIMED'; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # Add new columns to support claimable tasks
    op.add_column('automation_tasks', sa.Column('required_role', sa.String(length=100), nullable=True))
    op.add_column('automation_tasks', sa.Column('claimed_by_user_id', sa.Integer(), nullable=True))
    op.add_column('automation_tasks', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))

    # FK for claimed_by_user_id
    op.create_foreign_key('fk_automation_tasks_claimed_by_user', 'automation_tasks', 'users', ['claimed_by_user_id'], ['id'])

    # Map existing PENDING tasks to OPEN (safe migration); leave other statuses unchanged
    op.execute("UPDATE automation_tasks SET status='OPEN' WHERE status='PENDING'")

    # Change default for new tasks to OPEN
    op.alter_column(
        'automation_tasks',
        'status',
        existing_type=sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'OPEN', 'CLAIMED', name='automationtaskstatus', create_type=False),
        server_default=sa.text("'OPEN'")
    )


def downgrade() -> None:
    # Revert DEFAULT back to PENDING and map OPEN back to PENDING
    op.execute("UPDATE automation_tasks SET status='PENDING' WHERE status='OPEN'")
    op.alter_column(
        'automation_tasks',
        'status',
        existing_type=sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'OPEN', 'CLAIMED', name='automationtaskstatus', create_type=False),
        server_default=sa.text("'PENDING'")
    )

    # Drop FK and columns
    op.drop_constraint('fk_automation_tasks_claimed_by_user', 'automation_tasks', type_='foreignkey')
    op.drop_column('automation_tasks', 'claimed_at')
    op.drop_column('automation_tasks', 'claimed_by_user_id')
    op.drop_column('automation_tasks', 'required_role')

    # NOTE: we intentionally do not attempt to remove added enum labels. Removing enum labels in Postgres
    # is non-trivial and often unsafe; leaving them is safe for backwards compatibility.

"""Add automation engine tables (Phase 6.1)

Revision ID: 010
Revises: f93a4f97e6d0
Create Date: 2025-12-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010'
down_revision = 'f93a4f97e6d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types (with IF NOT EXISTS for idempotency)
    op.execute("DO $$ BEGIN CREATE TYPE automationtasktype AS ENUM ('RESTOCK', 'RETAIL', 'WHOLESALE', 'SALE', 'CUSTOM'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE automationtaskstatus AS ENUM ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE assignmentstatus AS ENUM ('PENDING', 'IN_PROGRESS', 'DONE', 'SKIPPED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE taskeventtype AS ENUM ('CREATED', 'ASSIGNED', 'STEP_STARTED', 'STEP_COMPLETED', 'REASSIGNED', 'CANCELLED', 'CLOSED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # Create automation_tasks table
    op.create_table(
        'automation_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.Enum('RESTOCK', 'RETAIL', 'WHOLESALE', 'SALE', 'CUSTOM', name='automationtasktype', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', name='automationtaskstatus', create_type=False), nullable=False, server_default='PENDING'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('related_order_id', sa.Integer(), nullable=True),
        sa.Column('task_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['related_order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_automation_tasks_id', 'automation_tasks', ['id'])
    op.create_index('ix_automation_tasks_status', 'automation_tasks', ['status'])
    op.create_index('ix_automation_tasks_type', 'automation_tasks', ['task_type'])
    op.create_index('ix_automation_tasks_created_by', 'automation_tasks', ['created_by_id'])

    # Create task_assignments table
    op.create_table(
        'task_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_hint', sa.String(100), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'DONE', 'SKIPPED', name='assignmentstatus', create_type=False), nullable=False, server_default='PENDING'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['automation_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'user_id', name='uq_task_user_assignment')
    )
    op.create_index('ix_task_assignments_id', 'task_assignments', ['id'])
    op.create_index('ix_task_assignments_task_id', 'task_assignments', ['task_id'])
    op.create_index('ix_task_assignments_user_id', 'task_assignments', ['user_id'])

    # Create task_events table
    op.create_table(
        'task_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.Enum('CREATED', 'ASSIGNED', 'STEP_STARTED', 'STEP_COMPLETED', 'REASSIGNED', 'CANCELLED', 'CLOSED', name='taskeventtype', create_type=False), nullable=False),
        sa.Column('event_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['automation_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_task_events_id', 'task_events', ['id'])
    op.create_index('ix_task_events_task_id', 'task_events', ['task_id'])
    op.create_index('ix_task_events_created_at', 'task_events', ['created_at'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('task_events')
    op.drop_table('task_assignments')
    op.drop_table('automation_tasks')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS taskeventtype")
    op.execute("DROP TYPE IF EXISTS assignmentstatus")
    op.execute("DROP TYPE IF EXISTS automationtaskstatus")
    op.execute("DROP TYPE IF EXISTS automationtasktype")

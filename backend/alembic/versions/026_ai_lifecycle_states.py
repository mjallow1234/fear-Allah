"""AI Phase 4.1 - Recommendation lifecycle states

Revision ID: 026
Revises: 025
Create Date: 2026-01-05

Adds lifecycle state management for AI recommendations:
- status: pending, acknowledged, approved, rejected, expired
- feedback_note: admin comments
- feedback_by_id: who provided feedback
- feedback_at: when feedback was given

NO EXECUTION - This is still read-only feedback system.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the AIRecommendationStatus enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE airecommendationstatus AS ENUM (
                'pending', 'acknowledged', 'approved', 'rejected', 'expired'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    # Add new columns to ai_recommendations table
    op.add_column(
        'ai_recommendations',
        sa.Column('status', sa.Enum(
            'pending', 'acknowledged', 'approved', 'rejected', 'expired',
            name='airecommendationstatus'
        ), server_default='pending', nullable=False)
    )
    
    op.add_column(
        'ai_recommendations',
        sa.Column('feedback_note', sa.Text(), nullable=True)
    )
    
    op.add_column(
        'ai_recommendations',
        sa.Column('feedback_by_id', sa.Integer(), nullable=True)
    )
    
    op.add_column(
        'ai_recommendations',
        sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add foreign key for feedback_by_id
    op.create_foreign_key(
        'fk_ai_recommendations_feedback_by',
        'ai_recommendations', 'users',
        ['feedback_by_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create index on status for filtering
    op.create_index(
        'ix_ai_recommendations_status',
        'ai_recommendations',
        ['status']
    )


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_ai_recommendations_status', table_name='ai_recommendations')
    
    # Remove foreign key
    op.drop_constraint('fk_ai_recommendations_feedback_by', 'ai_recommendations', type_='foreignkey')
    
    # Remove columns
    op.drop_column('ai_recommendations', 'feedback_at')
    op.drop_column('ai_recommendations', 'feedback_by_id')
    op.drop_column('ai_recommendations', 'feedback_note')
    op.drop_column('ai_recommendations', 'status')
    
    # Note: Not dropping enum type as it may still be referenced

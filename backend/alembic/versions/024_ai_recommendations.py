"""AI Recommendations Table

Revision ID: 024
Revises: 023
Create Date: 2026-01-05

Creates the ai_recommendations table for AI advisory system.
AI writes recommendations here - NEVER to business tables.

Safety Guarantee:
- AI reads from: sales, inventory, raw_materials, processing_batches, recipes
- AI writes ONLY to: ai_recommendations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


# revision identifiers, used by Alembic.
revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


# Define enums at module level (will NOT auto-create if already exists)
airecommendationtype = ENUM(
    'demand_forecast', 'production_plan', 'waste_alert', 
    'yield_insight', 'sales_insight', 'agent_insight',
    name='airecommendationtype',
    create_type=False
)

airecommendationscope = ENUM(
    'admin', 'storekeeper', 'agent', 'system',
    name='airecommendationscope',
    create_type=False
)

aigenerationmode = ENUM(
    'auto', 'on_demand',
    name='aigenerationmode', 
    create_type=False
)


def upgrade() -> None:
    # Create AI enums first using IF NOT EXISTS for safety
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE airecommendationtype AS ENUM (
                'demand_forecast', 'production_plan', 'waste_alert',
                'yield_insight', 'sales_insight', 'agent_insight'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE airecommendationscope AS ENUM (
                'admin', 'storekeeper', 'agent', 'system'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE aigenerationmode AS ENUM (
                'auto', 'on_demand'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    
    # Create ai_recommendations table
    op.create_table(
        'ai_recommendations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', airecommendationtype, nullable=False),
        sa.Column('scope', airecommendationscope, nullable=False, server_default='admin'),
        sa.Column('confidence', sa.Float(), nullable=True),  # 0.0 - 1.0
        sa.Column('summary', sa.String(500), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),  # JSON array of explanation points
        sa.Column('data_refs', sa.Text(), nullable=True),  # JSON object with referenced entity IDs
        sa.Column('generated_by', aigenerationmode, nullable=False, server_default='auto'),
        sa.Column('is_dismissed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('dismissed_by_id', sa.Integer(), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['dismissed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for efficient querying
    op.create_index('ix_ai_recommendations_type', 'ai_recommendations', ['type'])
    op.create_index('ix_ai_recommendations_scope', 'ai_recommendations', ['scope'])
    op.create_index('ix_ai_recommendations_generated_by', 'ai_recommendations', ['generated_by'])
    op.create_index('ix_ai_recommendations_created_at', 'ai_recommendations', ['created_at'])
    op.create_index('ix_ai_recommendations_is_dismissed', 'ai_recommendations', ['is_dismissed'])


def downgrade() -> None:
    op.drop_index('ix_ai_recommendations_is_dismissed', table_name='ai_recommendations')
    op.drop_index('ix_ai_recommendations_created_at', table_name='ai_recommendations')
    op.drop_index('ix_ai_recommendations_generated_by', table_name='ai_recommendations')
    op.drop_index('ix_ai_recommendations_scope', table_name='ai_recommendations')
    op.drop_index('ix_ai_recommendations_type', table_name='ai_recommendations')
    op.drop_table('ai_recommendations')
    op.execute('DROP TYPE IF EXISTS aigenerationmode')
    op.execute('DROP TYPE IF EXISTS airecommendationscope')
    op.execute('DROP TYPE IF EXISTS airecommendationtype')

"""AI governance tags (Phase 5.1)

Revision ID: 027
Revises: 026
Create Date: 2026-01-05

Adds governance tag fields to ai_recommendations:
- priority: critical, high, medium, low
- category: inventory, production, procurement, sales, operations, compliance
- risk_level: high_risk, medium_risk, low_risk, no_risk
- assigned_to_id: admin user who owns this recommendation
- tags: JSON array of custom tags
- governance_note: admin notes for governance
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade():
    # Create enums for governance tags
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE airecommendationpriority AS ENUM ('critical', 'high', 'medium', 'low');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE airecommendationcategory AS ENUM ('inventory', 'production', 'procurement', 'sales', 'operations', 'compliance');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE airisklevel AS ENUM ('high_risk', 'medium_risk', 'low_risk', 'no_risk');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Add governance tag columns
    op.add_column('ai_recommendations', sa.Column('priority', sa.Enum('critical', 'high', 'medium', 'low', name='airecommendationpriority', create_type=False), nullable=True))
    op.add_column('ai_recommendations', sa.Column('category', sa.Enum('inventory', 'production', 'procurement', 'sales', 'operations', 'compliance', name='airecommendationcategory', create_type=False), nullable=True))
    op.add_column('ai_recommendations', sa.Column('risk_level', sa.Enum('high_risk', 'medium_risk', 'low_risk', 'no_risk', name='airisklevel', create_type=False), nullable=True))
    op.add_column('ai_recommendations', sa.Column('assigned_to_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('ai_recommendations', sa.Column('tags', sa.Text(), nullable=True))
    op.add_column('ai_recommendations', sa.Column('governance_note', sa.Text(), nullable=True))
    
    # Add indexes for efficient filtering
    op.create_index('ix_ai_recommendations_priority', 'ai_recommendations', ['priority'])
    op.create_index('ix_ai_recommendations_category', 'ai_recommendations', ['category'])
    op.create_index('ix_ai_recommendations_risk_level', 'ai_recommendations', ['risk_level'])
    op.create_index('ix_ai_recommendations_assigned_to_id', 'ai_recommendations', ['assigned_to_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_ai_recommendations_assigned_to_id', table_name='ai_recommendations')
    op.drop_index('ix_ai_recommendations_risk_level', table_name='ai_recommendations')
    op.drop_index('ix_ai_recommendations_category', table_name='ai_recommendations')
    op.drop_index('ix_ai_recommendations_priority', table_name='ai_recommendations')
    
    # Drop columns
    op.drop_column('ai_recommendations', 'governance_note')
    op.drop_column('ai_recommendations', 'tags')
    op.drop_column('ai_recommendations', 'assigned_to_id')
    op.drop_column('ai_recommendations', 'risk_level')
    op.drop_column('ai_recommendations', 'category')
    op.drop_column('ai_recommendations', 'priority')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS airisklevel")
    op.execute("DROP TYPE IF EXISTS airecommendationcategory")
    op.execute("DROP TYPE IF EXISTS airecommendationpriority")

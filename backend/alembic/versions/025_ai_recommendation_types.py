"""AI Phase 9.2 - Add recommendation types

Revision ID: 025
Revises: 024
Create Date: 2026-01-05

Adds new recommendation types for Phase 9.2 Explainable Recommendations:
- production_recommendation
- reorder_recommendation  
- procurement_recommendation

Also adds 'recommendation' to aigenerationmode enum.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new values to airecommendationtype enum
    # Using ALTER TYPE ... ADD VALUE (PostgreSQL 9.1+)
    op.execute("ALTER TYPE airecommendationtype ADD VALUE IF NOT EXISTS 'production_recommendation';")
    op.execute("ALTER TYPE airecommendationtype ADD VALUE IF NOT EXISTS 'reorder_recommendation';")
    op.execute("ALTER TYPE airecommendationtype ADD VALUE IF NOT EXISTS 'procurement_recommendation';")
    
    # Add 'recommendation' to aigenerationmode enum
    op.execute("ALTER TYPE aigenerationmode ADD VALUE IF NOT EXISTS 'recommendation';")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values easily
    # Would need to recreate the type, which is risky with existing data
    # For safety, we leave the enum values in place on downgrade
    pass

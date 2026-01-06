"""Production reporting enhancements

Revision ID: 023
Revises: 022
Create Date: 2026-01-05

Adds:
- actual_waste_quantity to processing_batches for waste tracking
- expected_yield vs actual_yield tracking capability
- raw_materials_cost_snapshot for cost tracking at processing time
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add yield/waste tracking columns to processing_batches
    op.add_column('processing_batches',
        sa.Column('expected_quantity', sa.Integer(), nullable=True))
    op.add_column('processing_batches',
        sa.Column('actual_waste_quantity', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('processing_batches',
        sa.Column('waste_notes', sa.Text(), nullable=True))
    
    # Snapshot of raw materials used (JSON) for reporting
    op.add_column('processing_batches',
        sa.Column('raw_materials_used', sa.Text(), nullable=True))  # JSON snapshot
    
    # Yield efficiency percentage (actual / expected * 100)
    op.add_column('processing_batches',
        sa.Column('yield_efficiency', sa.Integer(), nullable=True))
    
    # Completed timestamp (separate from created_at for in-progress batches)
    op.add_column('processing_batches',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('processing_batches', 'completed_at')
    op.drop_column('processing_batches', 'yield_efficiency')
    op.drop_column('processing_batches', 'raw_materials_used')
    op.drop_column('processing_batches', 'waste_notes')
    op.drop_column('processing_batches', 'actual_waste_quantity')
    op.drop_column('processing_batches', 'expected_quantity')

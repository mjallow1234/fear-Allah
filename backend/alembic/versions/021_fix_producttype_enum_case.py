"""Fix ProductType enum case to lowercase

Revision ID: 021_fix_producttype_enum
Revises: 020_agriculture_processing
Create Date: 2026-01-05

Fixes the ProductType enum values to be lowercase for consistency
with all other enums in the codebase (UserStatus, OrderStatus, etc.)
"""
from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires a commit after adding new enum values before they can be used.
    # We need to use a different approach - recreate the enum type.
    
    # Step 1: Rename the column temporarily to avoid conflicts
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type DROP DEFAULT")
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type TYPE VARCHAR(50)")
    
    # Step 2: Update the data to lowercase
    op.execute("UPDATE inventory SET product_type = 'trade_good' WHERE product_type = 'TRADE_GOOD'")
    op.execute("UPDATE inventory SET product_type = 'raw_material' WHERE product_type = 'RAW_MATERIAL'")
    op.execute("UPDATE inventory SET product_type = 'finished_good' WHERE product_type = 'FINISHED_GOOD'")
    
    # Step 3: Drop old enum and create new one with lowercase values
    op.execute("DROP TYPE producttype")
    op.execute("CREATE TYPE producttype AS ENUM ('raw_material', 'finished_good', 'trade_good')")
    
    # Step 4: Convert column back to enum type
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type TYPE producttype USING product_type::producttype")
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type SET DEFAULT 'trade_good'")


def downgrade() -> None:
    # Revert to uppercase values
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type DROP DEFAULT")
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type TYPE VARCHAR(50)")
    
    op.execute("UPDATE inventory SET product_type = 'TRADE_GOOD' WHERE product_type = 'trade_good'")
    op.execute("UPDATE inventory SET product_type = 'RAW_MATERIAL' WHERE product_type = 'raw_material'")
    op.execute("UPDATE inventory SET product_type = 'FINISHED_GOOD' WHERE product_type = 'finished_good'")
    
    op.execute("DROP TYPE producttype")
    op.execute("CREATE TYPE producttype AS ENUM ('RAW_MATERIAL', 'FINISHED_GOOD', 'TRADE_GOOD')")
    
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type TYPE producttype USING product_type::producttype")
    op.execute("ALTER TABLE inventory ALTER COLUMN product_type SET DEFAULT 'TRADE_GOOD'")

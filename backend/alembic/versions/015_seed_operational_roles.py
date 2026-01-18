"""Seed operational roles (admin, agent, sales_agent, storekeeper, foreman, delivery)

Revision ID: 015
Revises: 014
Create Date: 2026-01-18
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None

OPERATIONAL_ROLES = [
    {"name": "admin", "description": "Operational admin role", "scope": "system", "is_system": True},
    {"name": "agent", "description": "Field agent role", "scope": "system", "is_system": False},
    {"name": "sales_agent", "description": "Sales agent role", "scope": "system", "is_system": False},
    {"name": "storekeeper", "description": "Storekeeper role", "scope": "system", "is_system": False},
    {"name": "foreman", "description": "Foreman role", "scope": "system", "is_system": False},
    {"name": "delivery", "description": "Delivery role", "scope": "system", "is_system": False},
]


def upgrade():
    conn = op.get_bind()
    for role in OPERATIONAL_ROLES:
        # Insert if missing
        result = conn.execute(sa.text("SELECT id FROM roles WHERE name = :name"), {"name": role["name"]})
        existing = result.fetchone()
        if not existing:
            conn.execute(
                sa.text("INSERT INTO roles (name, description, scope, is_system) VALUES (:name, :description, :scope, :is_system)"),
                {"name": role["name"], "description": role["description"], "scope": role["scope"], "is_system": role["is_system"]}
            )


def downgrade():
    # Do not remove roles on downgrade to avoid accidental data loss
    pass

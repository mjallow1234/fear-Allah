"""Phase 8.5.2 - Role & Permission Enhancements

Add description, is_system, created_at to roles.
Add key, description to permissions.
Seed initial permissions taxonomy.

Revision ID: 014_role_permission_enhancements
Revises: 013_audit_logs
Create Date: 2025-12-28
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision: str = '014'
down_revision: str = '013'
branch_labels = None
depends_on = None


# Initial permission taxonomy (Phase 8.5.2)
INITIAL_PERMISSIONS = [
    # System
    ("system.manage_users", "Manage user accounts (create, edit, deactivate)"),
    ("system.manage_roles", "Manage roles and permissions"),
    ("system.view_audit", "View audit logs"),
    ("system.manage_settings", "Manage system settings"),
    
    # Users
    ("user.create", "Create new users"),
    ("user.edit", "Edit user profiles"),
    ("user.deactivate", "Deactivate user accounts"),
    
    # Channels & Chat
    ("channel.create", "Create channels"),
    ("channel.delete", "Delete channels"),
    ("message.delete", "Delete any message"),
    ("message.pin", "Pin messages in channels"),
    
    # Sales / Orders
    ("sales.view", "View sales data"),
    ("sales.manage", "Create and manage sales"),
    ("orders.view", "View orders"),
    ("orders.manage", "Create and manage orders"),
]

# System roles with their permissions
SYSTEM_ROLES = [
    {
        "name": "system_admin",
        "description": "Full system administrator with all permissions",
        "scope": "system",
        "is_system": True,
        "permissions": [p[0] for p in INITIAL_PERMISSIONS],  # All permissions
    },
    {
        "name": "default",
        "description": "Default role for new users with basic permissions",
        "scope": "system", 
        "is_system": True,
        "permissions": ["channel.create", "sales.view", "orders.view"],  # Basic permissions
    },
]


def upgrade():
    # Add new columns to roles table
    op.add_column('roles', sa.Column('description', sa.String(500), nullable=True))
    op.add_column('roles', sa.Column('is_system', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('roles', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))
    
    # Add new columns to permissions table
    op.add_column('permissions', sa.Column('key', sa.String(100), nullable=True, unique=True))
    op.add_column('permissions', sa.Column('description', sa.String(500), nullable=True))
    
    # Create indexes
    op.create_index('ix_roles_is_system', 'roles', ['is_system'])
    op.create_index('ix_permissions_key', 'permissions', ['key'])
    
    # Update foreign keys with ON DELETE CASCADE
    # Drop existing foreign keys and recreate with cascade
    op.drop_constraint('role_permissions_role_id_fkey', 'role_permissions', type_='foreignkey')
    op.drop_constraint('role_permissions_permission_id_fkey', 'role_permissions', type_='foreignkey')
    op.create_foreign_key(
        'role_permissions_role_id_fkey', 
        'role_permissions', 'roles', 
        ['role_id'], ['id'], 
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'role_permissions_permission_id_fkey', 
        'role_permissions', 'permissions', 
        ['permission_id'], ['id'], 
        ondelete='CASCADE'
    )
    
    op.drop_constraint('user_roles_user_id_fkey', 'user_roles', type_='foreignkey')
    op.drop_constraint('user_roles_role_id_fkey', 'user_roles', type_='foreignkey')
    op.create_foreign_key(
        'user_roles_user_id_fkey',
        'user_roles', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'user_roles_role_id_fkey',
        'user_roles', 'roles',
        ['role_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Seed initial permissions
    conn = op.get_bind()
    
    # Insert permissions
    for key, description in INITIAL_PERMISSIONS:
        # Check if permission with this name or key already exists
        result = conn.execute(
            sa.text("SELECT id FROM permissions WHERE name = :name OR key = :key"),
            {"name": key, "key": key}
        )
        existing = result.fetchone()
        
        if existing:
            # Update existing permission
            conn.execute(
                sa.text("UPDATE permissions SET key = :key, description = :description WHERE id = :id"),
                {"key": key, "description": description, "id": existing[0]}
            )
        else:
            # Insert new permission
            conn.execute(
                sa.text("INSERT INTO permissions (name, key, description) VALUES (:name, :key, :description)"),
                {"name": key, "key": key, "description": description}
            )
    
    # Seed system roles
    for role_data in SYSTEM_ROLES:
        # Check if role exists
        result = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name"),
            {"name": role_data["name"]}
        )
        existing = result.fetchone()
        
        if existing:
            role_id = existing[0]
            # Update existing role
            conn.execute(
                sa.text("""
                    UPDATE roles 
                    SET description = :description, is_system = :is_system, scope = :scope
                    WHERE id = :id
                """),
                {
                    "description": role_data["description"],
                    "is_system": role_data["is_system"],
                    "scope": role_data["scope"],
                    "id": role_id,
                }
            )
        else:
            # Insert new role
            conn.execute(
                sa.text("""
                    INSERT INTO roles (name, description, scope, is_system)
                    VALUES (:name, :description, :scope, :is_system)
                """),
                {
                    "name": role_data["name"],
                    "description": role_data["description"],
                    "scope": role_data["scope"],
                    "is_system": role_data["is_system"],
                }
            )
            result = conn.execute(
                sa.text("SELECT id FROM roles WHERE name = :name"),
                {"name": role_data["name"]}
            )
            role_id = result.fetchone()[0]
        
        # Assign permissions to role
        for perm_key in role_data["permissions"]:
            # Get permission ID
            result = conn.execute(
                sa.text("SELECT id FROM permissions WHERE key = :key"),
                {"key": perm_key}
            )
            perm_row = result.fetchone()
            if perm_row:
                perm_id = perm_row[0]
                # Check if mapping exists
                result = conn.execute(
                    sa.text("SELECT 1 FROM role_permissions WHERE role_id = :role_id AND permission_id = :perm_id"),
                    {"role_id": role_id, "perm_id": perm_id}
                )
                if not result.fetchone():
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id)"),
                        {"role_id": role_id, "perm_id": perm_id}
                    )


def downgrade():
    # Drop indexes first
    op.drop_index('ix_roles_is_system', table_name='roles')
    op.drop_index('ix_permissions_key', table_name='permissions')
    
    # Drop columns
    op.drop_column('permissions', 'description')
    op.drop_column('permissions', 'key')
    op.drop_column('roles', 'created_at')
    op.drop_column('roles', 'is_system')
    op.drop_column('roles', 'description')
    
    # Note: Seeded data is not removed in downgrade

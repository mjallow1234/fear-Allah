"""
Backend Operational Permissions (Phase 3.1)

Read-only resolver that mirrors the UI permissions matrix. This module
provides a single place to look up operational permissions by role. It does
not enforce permissions - only computes and returns them for other systems
to consult.
"""
from typing import Dict, Any
from app.core.logging import api_logger

# Canonical operational permission matrix (read-only).
OPERATIONAL_PERMISSIONS: Dict[str, Dict[str, Any]] = {
    "admin": {
        "orders": ["read", "create", "update", "cancel"],
        "sales": ["read", "create", "overview", "transactions", "inventory", "raw_materials"],
        "tasks": ["read", "assign", "update"],
    },
    "agent": {
        "orders": ["read", "create"],
        "tasks": ["read", "update"],
    },
    "sales_agent": {
        "orders": ["read", "create"],
        "sales": ["read", "create"],
        "tasks": ["read"],
    },
    "storekeeper": {
        "orders": ["read", "create"],
        "sales": ["read", "create"],
        "tasks": ["read"],
    },
    "foreman": {
        "sales": ["read"],
        "tasks": ["read", "update"],
        "inventory": ["read"],
        "raw_materials": ["read"],
    },
    "delivery": {
        "tasks": ["read"],
    },
}


def resolve_permissions(user) -> Dict[str, Any]:
    """Resolve operational permissions for a user (read-only).

    Args:
        user: A user-like object with attributes `.operational_role_name` and
              `.is_system_admin` (booleans/strings). This function does not
              touch the database or modify the user.

    Returns:
        A dict mapping permission areas to allowed actions for the user's
        effective operational role. Returns an empty dict if no role.
    """
    try:
        role = None
        # System admins are operational admins at runtime
        if getattr(user, "is_system_admin", False):
            role = "admin"
        else:
            role = getattr(user, "operational_role_name", None)

        if not role:
            api_logger.debug(f"[PERMS] resolved permissions for user_id={getattr(user, 'id', 'unknown')} role=None -> {{}}")
            return {}

        # Normalise role name to lower-case and underscores to match keys
        norm_role = str(role).lower().replace(" ", "_")
        perms = OPERATIONAL_PERMISSIONS.get(norm_role, {})

        api_logger.debug(f"[PERMS] resolved permissions for user_id={getattr(user, 'id', 'unknown')} role={norm_role}")
        return perms
    except Exception as e:
        api_logger.debug(f"[PERMS] failed to resolve permissions for user_id={getattr(user, 'id', 'unknown')}: {e}")
        return {}

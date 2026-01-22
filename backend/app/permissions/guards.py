from fastapi import HTTPException, status
from app.permissions.operational_permissions import resolve_permissions
from app.core.logging import api_logger


def require_permission(user, resource: str, action: str):
    """Require that the given user has the specified permission for a resource.

    `user` should be a user-like object with attributes `operational_role_name` and `is_system_admin`.
    If the permission is not present, raise HTTP 403 and log an INFO-level event.
    """
    perms = resolve_permissions(user)
    allowed = perms.get(resource, [])
    if action not in allowed:
        # Log an info-level denial for audit/trace
        user_id = getattr(user, "id", getattr(user, "user_id", None))
        role = getattr(user, "operational_role_name", None)
        api_logger.info(f"[PERMS_DENIED] user_id={user_id} role={role} resource={resource} action={action}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not allowed to {action} {resource}"
        )

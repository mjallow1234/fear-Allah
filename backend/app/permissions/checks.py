"""
Reusable dependency helpers for endpoint-level enforcement.
Will be wired in Phase 5.2 — no usage yet.
"""
from fastapi import HTTPException, status

from .constants import Permission
from .roles import SystemRole, ChannelRole
from .service import permission_service


def require_permission(
    permission: Permission,
    system_role: SystemRole,
    channel_role: ChannelRole | None = None,
) -> None:
    """
    Raise 403 if user lacks the required permission.
    Call from endpoint after fetching user + membership.
    """
    effective = permission_service.get_effective_channel_permissions(
        system_role, channel_role
    )
    if permission not in effective:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission.value}",
        )

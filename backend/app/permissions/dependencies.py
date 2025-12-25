from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.permissions.constants import Permission
from app.permissions.service import PermissionService
from app.permissions.exceptions import PermissionDenied
from app.permissions.repository import get_system_roles, get_channel_roles
from app.core.security import get_current_user


def require_permission(
    permission: Permission,
    *,
    channel_param: str | None = None,
):
    async def dependency(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
        **kwargs,
    ):
        system_roles = await get_system_roles(db, user["user_id"])

        channel_roles = None
        if channel_param:
            channel_id = kwargs.get(channel_param)
            if channel_id is not None:
                channel_roles = await get_channel_roles(
                    db, user["user_id"], channel_id
                )

        allowed = PermissionService.has_permission(
            permission=permission,
            system_roles=system_roles,
            channel_roles=channel_roles,
        )

        if not allowed:
            raise PermissionDenied(permission.value)

        return True

    return dependency

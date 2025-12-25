from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import UserRole, ChannelRoleAssignment, Role
from app.permissions.roles import SystemRole, ChannelRole


async def get_system_roles(
    db: AsyncSession,
    user_id: int,
) -> list[SystemRole]:
    result = await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
        .where(Role.scope == "system")
    )
    return [SystemRole(r[0]) for r in result.all()]


async def get_channel_roles(
    db: AsyncSession,
    user_id: int,
    channel_id: int,
) -> list[ChannelRole]:
    result = await db.execute(
        select(Role.name)
        .join(ChannelRoleAssignment, ChannelRoleAssignment.role_id == Role.id)
        .where(ChannelRoleAssignment.user_id == user_id)
        .where(ChannelRoleAssignment.channel_id == channel_id)
        .where(Role.scope == "channel")
    )
    return [ChannelRole(r[0]) for r in result.all()]

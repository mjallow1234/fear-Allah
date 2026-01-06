"""
Demo onboarding for new users.
DEV-ONLY: Automatically adds newly registered users to all channels.

This ensures new users can immediately access channels without 403s.
Called from auth/register endpoint when APP_ENV=development.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Channel, Role, ChannelRoleAssignment, ChannelMember
from app.permissions.roles import ChannelRole
from app.core.config import settings, logger


async def onboard_demo_user(user_id: int, db: AsyncSession) -> dict:
    """
    Add a new user to all demo channels with member role.
    
    - Adds ChannelMember entries for all channels
    - Adds ChannelRoleAssignment with role=member for all channels
    - Idempotent: skips if entries already exist
    
    Args:
        user_id: The ID of the newly created user
        db: Database session
        
    Returns:
        dict with stats about what was created
    """
    stats = {
        "memberships_created": 0,
        "roles_assigned": 0,
        "skipped": 0,
    }
    
    # Get all channels
    result = await db.execute(select(Channel))
    channels = result.scalars().all()
    
    if not channels:
        logger.debug(f"[DemoOnboarding] No channels found for user {user_id}")
        return stats
    
    # Get the member role ID
    result = await db.execute(
        select(Role).where(Role.name == ChannelRole.MEMBER.value, Role.scope == "channel")
    )
    member_role = result.scalar_one_or_none()
    
    if not member_role:
        logger.warning("[DemoOnboarding] Member role not found - run demo_seeder first")
        return stats
    
    member_role_id = member_role.id
    
    for channel in channels:
        # --- Add ChannelMember if not exists ---
        result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.user_id == user_id,
                ChannelMember.channel_id == channel.id
            )
        )
        if not result.scalar_one_or_none():
            membership = ChannelMember(
                user_id=user_id,
                channel_id=channel.id
            )
            db.add(membership)
            stats["memberships_created"] += 1
        else:
            stats["skipped"] += 1
        
        # --- Add ChannelRoleAssignment if not exists ---
        result = await db.execute(
            select(ChannelRoleAssignment).where(
                ChannelRoleAssignment.user_id == user_id,
                ChannelRoleAssignment.channel_id == channel.id,
                ChannelRoleAssignment.role_id == member_role_id
            )
        )
        if not result.scalar_one_or_none():
            assignment = ChannelRoleAssignment(
                user_id=user_id,
                channel_id=channel.id,
                role_id=member_role_id
            )
            db.add(assignment)
            stats["roles_assigned"] += 1
    
    await db.commit()
    
    logger.info(
        f"[DemoOnboarding] User {user_id}: "
        f"{stats['memberships_created']} memberships, "
        f"{stats['roles_assigned']} roles assigned"
    )
    
    return stats


async def maybe_onboard_demo_user(user_id: int, db: AsyncSession) -> None:
    """
    Onboard user if APP_ENV=development.
    Safe to call from registration - does nothing in prod.
    """
    if settings.APP_ENV != "development":
        return
    
    await onboard_demo_user(user_id, db)

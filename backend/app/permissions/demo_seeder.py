"""
Demo seeder for RBAC channel roles and memberships.
DEV-ONLY: Seeds channel role assignments and memberships for all users.

This ensures demo users can read/write messages without 403s.
"""
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import User, Channel, Role, ChannelRoleAssignment, ChannelMember
from app.db.enums import ChannelType
from app.permissions.roles import ChannelRole
from app.core.config import settings, logger


async def seed_channel_roles(db: AsyncSession) -> dict:
    """
    Seed demo channel role assignments AND channel memberships.
    
    - First user (lowest ID) → owner on all channels
    - All other users → member on all channels
    - Also creates ChannelMember entries (required for channel access)
    - Skips existing assignments (idempotent)
    
    Returns dict with seeding stats.
    """
    stats = {
        "roles_created": 0,
        "assignments_created": 0,
        "memberships_created": 0,
        "skipped": 0,
        "users": [],
        "channels": [],
    }
    
    # 1. Ensure channel roles exist in roles table
    channel_roles_to_seed = [
        {"name": ChannelRole.OWNER.value, "scope": "channel"},
        {"name": ChannelRole.MODERATOR.value, "scope": "channel"},
        {"name": ChannelRole.MEMBER.value, "scope": "channel"},
        {"name": ChannelRole.GUEST.value, "scope": "channel"},
    ]
    
    for role_data in channel_roles_to_seed:
        # Check if role exists
        result = await db.execute(
            select(Role).where(Role.name == role_data["name"], Role.scope == role_data["scope"])
        )
        existing = result.scalar_one_or_none()
        if not existing:
            role = Role(name=role_data["name"], scope=role_data["scope"])
            db.add(role)
            stats["roles_created"] += 1
            logger.info(f"[DemoSeeder] Created role: {role_data['name']} (scope={role_data['scope']})")
    
    await db.commit()
    
    # 2. Get all users ordered by ID (first user becomes owner)
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    
    if not users:
        logger.warning("[DemoSeeder] No users found - nothing to seed")
        return stats
    
    # 3. Get all channels
    result = await db.execute(select(Channel))
    channels = result.scalars().all()
    
    if not channels:
        logger.warning("[DemoSeeder] No channels found - nothing to seed")
        return stats
    
    stats["users"] = [u.username for u in users]
    stats["channels"] = [c.name for c in channels]
    
    # 4. Get role IDs
    result = await db.execute(
        select(Role).where(Role.scope == "channel")
    )
    role_map = {r.name: r.id for r in result.scalars().all()}
    
    owner_role_id = role_map.get(ChannelRole.OWNER.value)
    member_role_id = role_map.get(ChannelRole.MEMBER.value)
    
    if not owner_role_id or not member_role_id:
        logger.error("[DemoSeeder] Missing required roles (owner/member)")
        return stats
    
    # 5. Assign roles AND memberships
    first_user = users[0]
    
    for channel in channels:
        # IMPORTANT: Auto-membership is restricted to PUBLIC channels only.
        # Private and Direct channels must have explicit membership.
        if channel.type != ChannelType.public.value:
            logger.debug(f"[DemoSeeder] Skipping auto-membership/role assignment for non-public channel: {channel.name} (type={channel.type})")
            continue

        for user in users:
            # --- Ensure ChannelMember exists (required for channel access) ---
            result = await db.execute(
                select(ChannelMember).where(
                    ChannelMember.user_id == user.id,
                    ChannelMember.channel_id == channel.id
                )
            )
            existing_membership = result.scalar_one_or_none()

            if not existing_membership:
                membership = ChannelMember(
                    user_id=user.id,
                    channel_id=channel.id
                )
                db.add(membership)
                stats["memberships_created"] += 1
                logger.debug(f"[DemoSeeder] Added membership: {user.username} → #{channel.name}")

            # --- Assign RBAC role ---
            # First user gets owner, others get member
            role_id = owner_role_id if user.id == first_user.id else member_role_id

            # Check if assignment exists
            result = await db.execute(
                select(ChannelRoleAssignment).where(
                    ChannelRoleAssignment.user_id == user.id,
                    ChannelRoleAssignment.channel_id == channel.id,
                    ChannelRoleAssignment.role_id == role_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                stats["skipped"] += 1
                continue

            # Create assignment
            assignment = ChannelRoleAssignment(
                user_id=user.id,
                channel_id=channel.id,
                role_id=role_id
            )
            db.add(assignment)
            stats["assignments_created"] += 1

            role_name = ChannelRole.OWNER.value if role_id == owner_role_id else ChannelRole.MEMBER.value
            logger.debug(f"[DemoSeeder] Assigned {user.username} → {role_name} on #{channel.name}")
    
    await db.commit()
    
    return stats


async def run_demo_seeder() -> None:
    """
    Run demo seeder if APP_ENV=development.
    Called from startup after default data seeding.
    """
    if settings.APP_ENV != "development":
        logger.info(f"[DemoSeeder] Skipping - APP_ENV={settings.APP_ENV} (not development)")
        return
    
    logger.info("[DemoSeeder] Running channel role seeding (APP_ENV=development)...")
    
    from app.db.database import async_session
    
    async with async_session() as db:
        stats = await seed_channel_roles(db)
    
    logger.info(
        f"[DemoSeeder] Complete: "
        f"{stats['roles_created']} roles created, "
        f"{stats['assignments_created']} role assignments created, "
        f"{stats['memberships_created']} memberships created, "
        f"{stats['skipped']} skipped (existing)"
    )
    
    if stats["users"]:
        logger.info(f"[DemoSeeder] Users: {', '.join(stats['users'])}")
    if stats["channels"]:
        logger.info(f"[DemoSeeder] Channels: {', '.join(stats['channels'])}")

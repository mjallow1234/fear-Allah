"""Backfill utilities for automation assignments.

Provides an async function to backfill placeholder TaskAssignment rows
by resolving active users for known roles (foreman, delivery).
"""
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import TaskAssignment, User
from app.core.config import logger


async def backfill_assignments(db: AsyncSession) -> int:
    """Backfill task_assignments.user_id for placeholders.

    Finds TaskAssignment rows where user_id IS NULL and role_hint in ('foreman','delivery'),
    finds an active User with matching User.role and sets the user_id accordingly.

    Returns the number of assignments updated.
    """
    updated = 0
    # Find placeholder assignments
    q = select(TaskAssignment).where(TaskAssignment.user_id == None).where(TaskAssignment.role_hint.in_(["foreman", "delivery"]))
    result = await db.execute(q)
    placeholders = result.scalars().all()

    for ph in placeholders:
        role = (ph.role_hint or "").lower()
        # Find active user with matching role
        r2 = await db.execute(
            select(User).where(User.is_active == True).where(User.role == role).order_by(User.id.asc()).limit(1)
        )
        user = r2.scalar_one_or_none()
        if user:
            ph.user_id = user.id
            db.add(ph)
            updated += 1
            logger.info(f"[Backfill] Assigned user {user.id} to placeholder assignment {ph.id} (role={role})")

    if updated:
        await db.commit()
    return updated

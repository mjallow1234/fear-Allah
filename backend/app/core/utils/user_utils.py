from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_user_display_name(db: AsyncSession, user_id: int) -> str:
    """Resolve a human-readable display name for a user ID."""
    if not user_id:
        return "System"

    user = await db.get(User, user_id)

    if not user:
        return f"User {user_id}"

    if user.display_name:
        return f"{user.display_name} ({user.username})"

    return user.username

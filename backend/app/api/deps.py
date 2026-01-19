from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User
from app.core.security import get_current_user as jwt_get_current_user


async def get_current_user(
    current_user_data: dict = Depends(jwt_get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve JWT-authenticated actor into DB User instance.

    This wraps the lower-level JWT dependency and returns a full User model
    (or raises 404) so route handlers can type `User = Depends(get_current_user)`.
    """
    user_id = current_user_data.get("user_id") if isinstance(current_user_data, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

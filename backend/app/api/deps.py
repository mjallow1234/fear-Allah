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
    try:
        user_id = current_user_data.get("user_id") if isinstance(current_user_data, dict) else None
        if not user_id:
            raise HTTPException(status_code=401, detail="Could not validate credentials")

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Attach operational role info onto the User object if one exists
        from app.db.models import UserRole as UserRoleModel, Role
        from app.api.system import OPERATIONAL_ROLE_NAMES

        op_result = await db.execute(
            select(UserRoleModel).join(Role).options(selectinload(UserRoleModel.role)).where(
                UserRoleModel.user_id == user.id, Role.name.in_(OPERATIONAL_ROLE_NAMES)
            )
        )
        op_assignment = op_result.scalar_one_or_none()
        user.operational_role_id = op_assignment.role_id if op_assignment else None
        user.operational_role_name = op_assignment.role.name if (op_assignment and op_assignment.role) else None
        return user
    except HTTPException:
        # Re-raise expected HTTP exceptions
        raise
    except Exception as e:
        # Log and convert unexpected errors into 401 so calling routes don't return 500
        from app.core.logging import api_logger
        from fastapi import status
        api_logger.exception(f"get_current_user failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

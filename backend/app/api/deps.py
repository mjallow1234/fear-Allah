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

        # Reject deleted accounts immediately.
        if getattr(user, 'deleted_at', None) is not None:
            # treat it as invalid credentials so calling routes return 401
            raise HTTPException(status_code=401, detail="Could not validate credentials")

        # Attach operational role info onto the User object if one exists
        from app.db.models import UserOperationalRole

        op_result = await db.execute(
            select(UserOperationalRole).where(UserOperationalRole.user_id == user.id)
        )
        op_roles = [r.role for r in op_result.scalars().all()]
        print("OPERATIONAL ROLES:", op_roles)
        # Use object.__setattr__ to bypass SA relationship instrumentation.
        # operational_roles on the model is a relationship (UserOperationalRole objects);
        # we shadow it here with a plain string list so callers can do:
        #   any(role in allowed_roles for role in user.operational_roles)
        object.__setattr__(user, 'operational_roles', op_roles)
        user.operational_role_name = op_roles[0] if op_roles else None
        user.operational_role_id = None
        return user
    except HTTPException:
        # Re-raise expected HTTP exceptions
        raise
    except Exception as e:
        # Log and convert unexpected errors into 401 so calling routes don't return 500
        from app.core.logging import api_logger
        from fastapi import status
        api_logger.error(
            "get_current_user failed",
            error=str(e),
            exc_type=type(e).__name__,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

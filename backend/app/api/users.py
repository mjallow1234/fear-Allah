from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, List

from app.db.database import get_db
from app.db.models import User, UserStatus, UserRole as UserRoleModel, Role, RolePermission
from app.core.security import get_current_user

router = APIRouter()


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    status: str
    is_system_admin: bool
    last_login_at: Optional[str] = None
    preferences: Optional[dict] = None

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: Optional[str] = None


# Phase 2.5: User Preferences
class UserPreferences(BaseModel):
    """User preferences schema with strict validation."""
    dark_mode: bool = True
    compact_mode: bool = False
    notifications: bool = True
    sound: bool = True

    class Config:
        extra = "forbid"  # Reject unknown fields


class UserPreferencesResponse(BaseModel):
    preferences: UserPreferences


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status.value if hasattr(user.status, 'value') else user.status,
        is_system_admin=user.is_system_admin,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    request: UserUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if request.display_name is not None:
        user.display_name = request.display_name
    if request.avatar_url is not None:
        user.avatar_url = request.avatar_url
    if request.status is not None:
        from app.db.enums import UserStatus
        try:
            user.status = UserStatus(request.status).value
        except Exception:
            pass
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status.value if hasattr(user.status, 'value') else user.status,
        is_system_admin=user.is_system_admin,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
    )


# Phase 2.5: User Preferences Endpoints
@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's preferences."""
    query = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Return stored preferences or defaults
    if user.preferences:
        prefs = UserPreferences(**user.preferences)
    else:
        prefs = UserPreferences()

    return UserPreferencesResponse(preferences=prefs)


@router.put("/me/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    request: UserPreferences,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user's preferences (merges with existing)."""
    query = select(User).where(User.id == current_user["user_id"])
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Merge with existing preferences (don't overwrite unset fields)
    existing = user.preferences or {}
    merged = {**existing, **request.model_dump()}
    user.preferences = merged
    await db.commit()
    await db.refresh(user)

    return UserPreferencesResponse(preferences=UserPreferences(**merged))


def _serialize_user(user: User) -> dict:
    """Return a JSON-serializable dict for a User, safe for responses."""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "status": user.status.value if hasattr(user.status, 'value') else (user.status if user.status is not None else None),
        "is_system_admin": user.is_system_admin,
        "last_login_at": user.last_login_at.isoformat() if getattr(user, 'last_login_at', None) else None,
        "preferences": dict(user.preferences) if getattr(user, 'preferences', None) else None,
    }


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.is_active == True).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    return [_serialize_user(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return _serialize_user(user)


# Phase 8.6: Get current user's permissions
@router.get("/me/permissions")
async def get_current_user_permissions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current user's permissions based on their assigned roles.
    System admins get all permissions.
    """
    user_id = current_user["user_id"]
    
    # Fetch user to check is_system_admin
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # System admins have all permissions
    if user.is_system_admin:
        return {
            "is_system_admin": True,
            "permissions": [
                "system.manage_users",
                "system.manage_roles", 
                "system.view_audit",
                "system.manage_settings",
                "channel.create",
                "channel.delete",
                "channel.manage",
                "message.delete_any",
                "user.ban",
                "user.mute",
            ]
        }
    
    # Get permissions from user's assigned roles
    permissions = set()
    
    # Query user's roles with their permissions
    result = await db.execute(
        select(UserRoleModel)
        .options(
            selectinload(UserRoleModel.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission)
        )
        .where(UserRoleModel.user_id == user_id)
    )
    user_roles = result.scalars().all()
    
    for user_role in user_roles:
        if user_role.role and user_role.role.permissions:
            for rp in user_role.role.permissions:
                if rp.permission and rp.permission.key:
                    permissions.add(rp.permission.key)
    
    return {
        "is_system_admin": False,
        "permissions": sorted(list(permissions))
    }


@router.get("/by-username/{username}", response_model=UserResponse)
async def get_user_by_username(
    username: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.username == username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

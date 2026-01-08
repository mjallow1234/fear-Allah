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

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: Optional[str] = None


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
    
    return user


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
    return user


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
    return users


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
    
    return user


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
        .options(selectinload(UserRoleModel.role).selectinload(Role.permissions).selectinload(RolePermission.permission))
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


@router.get("/me/teams")
async def get_my_teams(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return list of teams the current user is a member of."""
    user_id = current_user["user_id"]
    from app.db.models import TeamMember, Team
    query = select(Team).join(TeamMember, Team.id == TeamMember.team_id).where(TeamMember.user_id == user_id)
    result = await db.execute(query)
    teams = result.scalars().all()
    return [
        {"id": t.id, "name": t.name, "display_name": t.display_name} for t in teams
    ]
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

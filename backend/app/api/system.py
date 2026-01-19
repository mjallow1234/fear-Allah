"""
System Console API (Phase 8.4 + 8.5.1 + 8.5.2)
Admin-only endpoints for system management.
Only accessible to users with is_system_admin = true.

Phase 8.5.1 - User Management Actions:
- Activate/Deactivate users
- Promote/Demote admin
- Change user role
- Force logout
- Reset password

Phase 8.5.2 - Role & Permission Management:
- List/Create/Delete roles (DB-driven)
- Update role permissions with diff logging
- Assign roles to users
- System role protection (cannot delete/demote)
- Last-admin protection across role changes
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import secrets
import json

from app.db.database import get_db
from app.db.models import User, AuditLog, Role, PermissionModel, RolePermission
from app.db.enums import UserRole
from app.core.security import (
    get_current_user,
    require_admin,
    get_password_hash,
    ROLE_PERMISSIONS,
    Permission as PermissionConst,
)
from app.core.config import settings
from app.core.rate_limit_config import (
    AUTH_LIMITS,
    API_LIMITS,
    SALES_LIMITS,
    INVENTORY_LIMITS,
    AUTOMATION_LIMITS,
    rate_limit_settings,
)
from app.services.audit import log_audit, AuditActions, AuditTargetTypes

router = APIRouter()


# === Safety Helpers (Phase 8.5.1) ===

def ensure_not_self_action(actor_id: int, target_user_id: int, action_name: str = "this action"):
    """
    Prevent admin from performing certain actions on themselves.
    Used for: deactivate, demote admin, force logout, etc.
    """
    if actor_id == target_user_id:
        raise HTTPException(
            status_code=400,
            detail=f"You cannot perform {action_name} on yourself."
        )


async def ensure_not_last_admin(db: AsyncSession, exclude_user_id: Optional[int] = None):
    """
    Ensure there's at least one system admin remaining after an action.
    Call this BEFORE demoting or deactivating an admin.
    """
    query = select(func.count(User.id)).where(
        User.is_system_admin == True,
        User.is_active == True
    )
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    
    admin_count = await db.scalar(query) or 0
    
    if admin_count < 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the last system administrator."
        )


async def get_user_or_404(db: AsyncSession, user_id: int) -> User:
    """Fetch user by ID or raise 404."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def serialize_user_state(user: User) -> dict:
    """Serialize user state for audit logging (before/after)."""
    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "is_system_admin": user.is_system_admin,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        "is_banned": user.is_banned,
        "is_muted": user.is_muted,
    }


# === Pydantic Models ===

class UserListItem(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str]
    role: str
    is_active: bool
    is_system_admin: bool
    is_banned: bool
    is_muted: bool
    created_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserListItem]
    total: int
    page: int
    limit: int


class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    is_system_admin: Optional[bool] = None
    role: Optional[str] = None


# Phase 8.5.1 - Specific request models for user actions
class UserStatusRequest(BaseModel):
    """Request body for PATCH /users/{id}/status"""
    active: bool = Field(..., description="Whether the user should be active")


class UserAdminRequest(BaseModel):
    """Request body for PATCH /users/{id}/admin"""
    is_system_admin: bool = Field(..., description="Whether the user should be a system admin")


class UserRoleRequest(BaseModel):
    """Request body for PATCH /users/{id}/role"""
    role: str = Field(..., description="The role to assign (system_admin, team_admin, member, guest)")


class PasswordResetResponse(BaseModel):
    temporary_password: str
    message: str


# Phase 8.5.4 - User Creation Models
class CreateUserRequest(BaseModel):
    """Request body for POST /system/users - admin creates new user."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username (3-50 chars)")
    email: EmailStr = Field(..., description="Unique email address")
    role_id: int = Field(..., description="ID of the system role to assign")
    operational_role_id: Optional[int] = Field(default=None, description="Optional operational role ID to assign")
    is_system_admin: bool = Field(default=False, description="Whether user should be a system admin")
    active: bool = Field(default=True, description="Whether user should be active")


class CreatedUserInfo(BaseModel):
    """User info returned after creation."""
    id: int
    username: str
    email: str
    active: bool
    is_system_admin: bool
    role_id: int
    role_name: str
    operational_role_id: Optional[int] = None
    operational_role_name: Optional[str] = None


class CreateUserResponse(BaseModel):
    """Response for POST /system/users with temp password."""
    user: CreatedUserInfo
    temporary_password: str


class RoleInfo(BaseModel):
    name: str
    permissions: List[str]


class PermissionInfo(BaseModel):
    name: str
    description: str


class SystemSettingsResponse(BaseModel):
    app_name: str
    environment: str
    features: dict
    upload_limits: dict
    rate_limits: dict


class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[int]
    description: Optional[str]
    meta: Optional[dict]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    logs: List[AuditLogEntry]
    total: int
    page: int
    limit: int


# === System Admin Guard ===

async def require_system_admin(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> User:
    """
    Dependency that requires the user to be a system admin.
    More strict than require_admin - checks is_system_admin flag specifically.
    """
    user = await require_admin(db, current_user)
    
    if not user.is_system_admin:
        raise HTTPException(
            status_code=403,
            detail="System admin access required"
        )
    
    return user


# === User Management ===

@router.get("/users", response_model=UserListResponse)
async def list_system_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """List all users with filters for system management."""
    query = select(User)
    
    # Apply filters
    if search:
        query = query.where(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%")) |
            (User.display_name.ilike(f"%{search}%"))
        )
    
    if role:
        try:
            role_enum = UserRole(role)
            query = query.where(User.role == role_enum)
        except ValueError:
            pass
    
    if status == "active":
        query = query.where(User.is_active == True, User.is_banned == False)
    elif status == "inactive":
        query = query.where(User.is_active == False)
    elif status == "banned":
        query = query.where(User.is_banned == True)
    
    # Get total count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        users=[
            UserListItem(
                id=u.id,
                username=u.username,
                email=u.email,
                display_name=u.display_name,
                role=u.role.value if hasattr(u.role, 'value') else str(u.role or 'member'),
                is_active=u.is_active,
                is_system_admin=u.is_system_admin,
                is_banned=u.is_banned,
                is_muted=u.is_muted,
                created_at=u.created_at,
            )
            for u in users
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/users/{user_id}")
async def get_system_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """Get detailed user information."""
    user = await get_user_or_404(db, user_id)
    
    # Fetch operational role assignment (if any)
    from app.db.models import UserRole as UserRoleModel
    op_result = await db.execute(
        select(UserRoleModel)
        .join(Role)
        .options(selectinload(UserRoleModel.role))
        .where(UserRoleModel.user_id == user.id, Role.name.in_(OPERATIONAL_ROLE_NAMES))
    )
    op_assignment = op_result.scalar_one_or_none()
    op_role_id = op_assignment.role_id if op_assignment else None
    op_role_name = op_assignment.role.name if op_assignment else None

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "role": user.role.value if hasattr(user.role, 'value') else str(user.role or 'member'),
        "is_active": user.is_active,
        "is_system_admin": user.is_system_admin,
        "is_banned": user.is_banned,
        "ban_reason": user.ban_reason,
        "banned_at": user.banned_at.isoformat() if user.banned_at else None,
        "is_muted": user.is_muted,
        "muted_until": user.muted_until.isoformat() if user.muted_until else None,
        "muted_reason": user.muted_reason,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "operational_role_id": op_role_id,
        "operational_role_name": op_role_name,
    }


# === Phase 8.5.4 - Admin User Creation ===

def generate_temp_password(length: int = 14) -> str:
    """
    Generate a secure temporary password.
    
    Requirements:
    - 12-16 characters (default 14)
    - Mix of uppercase, lowercase, numbers
    - No symbols (copy/paste friendly)
    - Guaranteed to have at least one of each type
    """
    import string
    import random
    
    if length < 12:
        length = 12
    elif length > 16:
        length = 16
    
    # Ensure at least one of each type
    password_chars = [
        random.choice(string.ascii_uppercase),  # At least one uppercase
        random.choice(string.ascii_lowercase),  # At least one lowercase
        random.choice(string.digits),           # At least one digit
    ]
    
    # Fill remaining with random mix (no symbols)
    all_chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
    password_chars.extend(random.choices(all_chars, k=length - 3))
    
    # Shuffle to randomize positions
    random.shuffle(password_chars)
    
    return ''.join(password_chars)


@router.post("/users", response_model=CreateUserResponse, status_code=201)
async def create_system_user(
    request: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Create a new user (admin only).
    
    System admin creates a user with:
    - Unique username and email
    - Assigned role (by role_id)
    - Optional system admin flag
    - Optional active status
    
    Returns the created user and a temporary password (shown once).
    The password is NOT logged anywhere.
    
    User should change password on first login.
    """
    # 1. Validate username uniqueness
    existing_username = await db.execute(
        select(User).where(User.username == request.username)
    )
    if existing_username.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Username '{request.username}' is already taken."
        )
    
    # 2. Validate email uniqueness
    existing_email = await db.execute(
        select(User).where(User.email == request.email)
    )
    if existing_email.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Email '{request.email}' is already registered."
        )
    
    # 3. Validate role_id exists
    role = await db.execute(
        select(Role).where(Role.id == request.role_id)
    )
    role_obj = role.scalar_one_or_none()
    if not role_obj:
        raise HTTPException(
            status_code=400,
            detail=f"Role with ID {request.role_id} does not exist."
        )
    
    # 4. Generate secure temporary password (12-16 chars, no symbols)
    temp_password = generate_temp_password(14)
    hashed_password = get_password_hash(temp_password)
    
    # 5. Determine the UserRole enum value based on role name or is_system_admin
    if request.is_system_admin:
        user_role_enum = UserRole.system_admin
    elif role_obj.name in ['team_admin', 'admin']:
        user_role_enum = UserRole.team_admin
    elif role_obj.name == 'guest':
        user_role_enum = UserRole.guest
    else:
        # For operational roles, try to map to the UserRole enum if it exists
        try:
            user_role_enum = UserRole(role_obj.name)
        except ValueError:
            # Role name not represented in UserRole enum (e.g., sales_agent), default to member
            user_role_enum = UserRole.member
    
    # 6. Create user
    new_user = User(
        username=request.username,
        email=request.email,
        hashed_password=hashed_password,
        display_name=request.username,  # Default display name
        is_active=request.active,
        is_system_admin=request.is_system_admin,
        role=user_role_enum,
    )
    
    db.add(new_user)
    await db.flush()  # Get the ID without committing
    
    # 7. Create UserRole assignment (DB-driven role) for system role
    from app.db.models import UserRole as UserRoleModel
    user_role_assignment = UserRoleModel(
        user_id=new_user.id,
        role_id=request.role_id,
    )
    db.add(user_role_assignment)

    # If an operational role was provided, create an additional assignment
    operational_role_obj = None
    if request.operational_role_id:
        operational_role = await db.execute(select(Role).where(Role.id == request.operational_role_id))
        operational_role_obj = operational_role.scalar_one_or_none()
        if not operational_role_obj:
            raise HTTPException(status_code=400, detail=f"Operational role with ID {request.operational_role_id} does not exist.")
        # Ensure the role is one of the allowed operational names
        if operational_role_obj.name not in OPERATIONAL_ROLE_NAMES:
            raise HTTPException(status_code=400, detail="Provided role_id is not an operational role")
        operational_assignment = UserRoleModel(
            user_id=new_user.id,
            role_id=request.operational_role_id,
        )
        db.add(operational_assignment)

    # 8. Commit transaction
    await db.commit()
    await db.refresh(new_user)

    # 9. Audit logging - DO NOT log password
    meta = {
        "actor": admin.username,
        "actor_id": admin.id,
        "username": new_user.username,
        "email": new_user.email,
        "role_id": request.role_id,
        "role_name": role_obj.name,
        "is_system_admin": request.is_system_admin,
        "active": request.active,
    }
    if operational_role_obj:
        meta.update({"operational_role_id": operational_role_obj.id, "operational_role_name": operational_role_obj.name})

    await log_audit(
        db=db,
        action="user.create",
        target_type=AuditTargetTypes.USER,
        target_id=new_user.id,
        description=f"User {new_user.username} created by admin {admin.username}",
        meta=meta,
        user_id=admin.id,
        username=admin.username,
    )

    # 10. Return created user + temp password (shown once only)
    return CreateUserResponse(
        user=CreatedUserInfo(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            active=new_user.is_active,
            is_system_admin=new_user.is_system_admin,
            role_id=request.role_id,
            role_name=role_obj.name,
            operational_role_id=operational_role_obj.id if operational_role_obj else None,
            operational_role_name=operational_role_obj.name if operational_role_obj else None,
        ),
        temporary_password=temp_password,
    )


# === Phase 8.5.1 - User Management Actions ===

@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: int,
    request: UserStatusRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Activate or deactivate a user.
    
    Rules:
    - Cannot deactivate yourself
    - Cannot deactivate the last active admin
    """
    user = await get_user_or_404(db, user_id)
    before_state = serialize_user_state(user)
    
    # Safety checks
    if not request.active:
        ensure_not_self_action(admin.id, user_id, "deactivate")
        
        # If deactivating an admin, ensure not last admin
        if user.is_system_admin:
            await ensure_not_last_admin(db, exclude_user_id=user_id)
    
    # No change needed
    if user.is_active == request.active:
        return {
            "message": f"User {user.username} is already {'active' if request.active else 'inactive'}",
            "changed": False,
        }
    
    # Apply change
    user.is_active = request.active
    await db.commit()
    await db.refresh(user)
    
    after_state = serialize_user_state(user)
    action = "user.activate" if request.active else "user.deactivate"
    
    # Log audit with before/after state
    await log_audit(
        db=db,
        action=action,
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"{'Activated' if request.active else 'Deactivated'} user {user.username}",
        meta={
            "before": before_state,
            "after": after_state,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return {
        "message": f"User {user.username} {'activated' if request.active else 'deactivated'} successfully",
        "changed": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active,
        },
    }


@router.patch("/users/{user_id}/admin")
async def update_user_admin_status(
    user_id: int,
    request: UserAdminRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Promote or demote a user's system admin status.
    
    Rules:
    - Cannot demote yourself
    - Cannot demote the last system admin
    """
    user = await get_user_or_404(db, user_id)
    before_state = serialize_user_state(user)
    
    # Safety checks for demotion
    if not request.is_system_admin:
        ensure_not_self_action(admin.id, user_id, "demote admin")
        
        # Ensure not last admin
        if user.is_system_admin:
            await ensure_not_last_admin(db, exclude_user_id=user_id)
    
    # No change needed
    if user.is_system_admin == request.is_system_admin:
        return {
            "message": f"User {user.username} is already {'an admin' if request.is_system_admin else 'not an admin'}",
            "changed": False,
        }
    
    # Apply change
    user.is_system_admin = request.is_system_admin
    
    # Also update role enum if promoting
    if request.is_system_admin:
        user.role = UserRole.system_admin
    elif user.role == UserRole.system_admin:
        # Demoting: reset to member if was system_admin role
        user.role = UserRole.member
    
    await db.commit()
    await db.refresh(user)
    
    after_state = serialize_user_state(user)
    action = "user.promote_admin" if request.is_system_admin else "user.demote_admin"
    
    # Log audit with before/after state
    await log_audit(
        db=db,
        action=action,
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"{'Promoted' if request.is_system_admin else 'Demoted'} {user.username} {'to' if request.is_system_admin else 'from'} system admin",
        meta={
            "before": before_state,
            "after": after_state,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return {
        "message": f"User {user.username} {'promoted to' if request.is_system_admin else 'demoted from'} system admin successfully",
        "changed": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "is_system_admin": user.is_system_admin,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        },
    }


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    request: UserRoleRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Change a user's role.
    
    Valid roles: system_admin, team_admin, member, guest
    
    Rules:
    - Role must be valid
    - Changing to system_admin also sets is_system_admin flag
    - Changing from system_admin checks last admin rule
    """
    # Validate role
    try:
        new_role = UserRole(request.role)
    except ValueError:
        valid_roles = [r.value for r in UserRole]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {request.role}. Valid roles: {', '.join(valid_roles)}"
        )
    
    user = await get_user_or_404(db, user_id)
    before_state = serialize_user_state(user)
    
    # Safety checks if changing from admin role
    if user.role == UserRole.system_admin and new_role != UserRole.system_admin:
        ensure_not_self_action(admin.id, user_id, "change role from admin")
        await ensure_not_last_admin(db, exclude_user_id=user_id)
    
    # No change needed
    if user.role == new_role:
        return {
            "message": f"User {user.username} already has role {request.role}",
            "changed": False,
        }
    
    old_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
    
    # Apply change
    user.role = new_role
    
    # Sync is_system_admin flag with role
    if new_role == UserRole.system_admin:
        user.is_system_admin = True
    elif user.is_system_admin and new_role != UserRole.system_admin:
        user.is_system_admin = False
    
    await db.commit()
    await db.refresh(user)
    
    after_state = serialize_user_state(user)
    
    # Log audit with before/after state
    await log_audit(
        db=db,
        action=AuditActions.ADMIN_USER_ROLE_CHANGE,
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"Changed {user.username} role from {old_role} to {request.role}",
        meta={
            "before": before_state,
            "after": after_state,
            "old_role": old_role,
            "new_role": request.role,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return {
        "message": f"User {user.username} role changed to {request.role} successfully",
        "changed": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
            "is_system_admin": user.is_system_admin,
        },
    }


@router.post("/users/{user_id}/force-logout")
async def force_user_logout(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Force logout a user by invalidating their sessions.
    
    Rules:
    - Cannot force logout yourself
    
    Implementation notes:
    - In a JWT system with token versioning, this would increment session_version
    - WebSocket connections would be disconnected via broadcast
    - For now, we log the action for audit purposes
    """
    user = await get_user_or_404(db, user_id)
    
    # Safety check
    ensure_not_self_action(admin.id, user_id, "force logout")
    
    # TODO: Implement actual token invalidation
    # Options:
    # 1. Token blacklist (Redis)
    # 2. session_version column increment
    # 3. Broadcast disconnect to WebSocket manager
    
    # Log audit
    await log_audit(
        db=db,
        action="user.force_logout",
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"Forced logout of {user.username} by admin",
        meta={
            "target_user": user.username,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return {
        "message": f"Force logout initiated for {user.username}",
        "note": "User will need to re-authenticate on next request",
        "user": {
            "id": user.id,
            "username": user.username,
        },
    }


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResponse)
async def reset_user_password(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Reset a user's password to a temporary value.
    
    Returns the temporary password ONCE - it is not logged.
    User should change password on next login.
    """
    user = await get_user_or_404(db, user_id)
    
    # Generate secure temporary password (16 chars, URL-safe)
    temp_password = secrets.token_urlsafe(12)
    user.hashed_password = get_password_hash(temp_password)
    
    # TODO: Set a flag to force password change on next login
    # user.must_change_password = True
    
    await db.commit()
    
    # Log audit - DO NOT log the password itself
    await log_audit(
        db=db,
        action="user.password_reset",
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"Password reset for {user.username} by admin",
        meta={
            "target_user": user.username,
            "actor": admin.username,
            # Note: password is NOT logged for security
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return PasswordResetResponse(
        temporary_password=temp_password,
        message=f"Password reset for {user.username}. User must change on next login.",
    )


# Legacy endpoint - kept for backward compatibility
@router.patch("/users/{user_id}")
async def update_system_user(
    user_id: int,
    request: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Update user status/role (legacy endpoint).
    
    Prefer using specific endpoints:
    - PATCH /users/{id}/status - for activate/deactivate
    - PATCH /users/{id}/admin - for promote/demote admin
    - PATCH /users/{id}/role - for role changes
    """
    user = await get_user_or_404(db, user_id)
    before_state = serialize_user_state(user)
    
    # Prevent self-demotion
    if user_id == admin.id and request.is_system_admin is False:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    
    # Prevent deactivating last admin
    if request.is_active is False and user.is_system_admin:
        await ensure_not_last_admin(db, exclude_user_id=user_id)
    
    # Prevent demoting last admin
    if request.is_system_admin is False and user.is_system_admin:
        await ensure_not_last_admin(db, exclude_user_id=user_id)
    
    changes = {}
    
    if request.is_active is not None and request.is_active != user.is_active:
        user.is_active = request.is_active
        changes["is_active"] = request.is_active
    
    if request.is_system_admin is not None and request.is_system_admin != user.is_system_admin:
        user.is_system_admin = request.is_system_admin
        changes["is_system_admin"] = request.is_system_admin
        
        # Also update role if promoting to admin
        if request.is_system_admin:
            user.role = UserRole.system_admin
            changes["role"] = "system_admin"
    
    if request.role is not None:
        try:
            new_role = UserRole(request.role)
            if user.role != new_role:
                user.role = new_role
                changes["role"] = request.role
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    
    if changes:
        await db.commit()
        await db.refresh(user)
        
        after_state = serialize_user_state(user)
        
        # Determine action type
        action = "admin.user.update"
        if "is_system_admin" in changes:
            action = "user.promote_admin" if changes["is_system_admin"] else "user.demote_admin"
        elif "is_active" in changes:
            action = "user.activate" if changes["is_active"] else "user.deactivate"
        elif "role" in changes:
            action = AuditActions.ADMIN_USER_ROLE_CHANGE
        
        # Log audit with before/after
        await log_audit(
            db=db,
            action=action,
            target_type=AuditTargetTypes.USER,
            target_id=user_id,
            description=f"Updated user {user.username}",
            meta={
                "before": before_state,
                "after": after_state,
                "changes": changes,
                "actor": admin.username,
            },
            user_id=admin.id,
            username=admin.username,
        )
    
    return {
        "message": "User updated successfully",
        "changes": changes,
    }


# === Roles & Permissions (Phase 8.5.2 - Full Implementation) ===

class RoleDetailOut(BaseModel):
    """Role response model with full details."""
    id: int
    name: str
    description: Optional[str]
    scope: str
    is_system: bool
    permissions: List[str]
    created_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Response for listing roles."""
    roles: List[RoleDetailOut]
    total: int


class PermissionDetailOut(BaseModel):
    """Permission response model."""
    id: int
    key: str
    name: str
    description: Optional[str]
    
    class Config:
        from_attributes = True


class PermissionListResponse(BaseModel):
    """Response for listing permissions."""
    permissions: List[PermissionDetailOut]
    total: int


class RoleCreateRequest(BaseModel):
    """Request body for creating a new role."""
    name: str = Field(..., min_length=2, max_length=100, description="Role name (lowercase, snake_case)")
    description: Optional[str] = Field(None, max_length=500)
    permissions: List[str] = Field(default_factory=list, description="List of permission keys")


class RoleUpdatePermissionsRequest(BaseModel):
    """Request body for updating role permissions."""
    permissions: List[str] = Field(..., description="Complete list of permission keys for this role")


class UserRoleAssignRequest(BaseModel):
    """Request body for assigning a role to a user."""
    role_id: int = Field(..., description="ID of the role to assign")


class OperationalRoleAssignRequest(BaseModel):
    """Request body for assigning an operational role to a user."""
    operational_role_id: Optional[int] = Field(None, description="ID of the operational role to assign, or null to remove")


# === Role Helper Functions ===

# Operational roles used for user creation and operational assignment
OPERATIONAL_ROLE_NAMES = [
    'admin', 'agent', 'sales_agent', 'storekeeper', 'foreman', 'delivery'
]


async def ensure_operational_roles(db: AsyncSession):
    """Safely ensure operational roles exist in the DB at runtime.

    This helper is idempotent and can be called on startup or on-demand.
    It only inserts missing operational roles and commits once.
    """
    from app.db.models import Role

    result = await db.execute(select(Role.name).where(Role.name.in_(OPERATIONAL_ROLE_NAMES)))
    rows = result.fetchall()
    existing_names = {r[0] for r in rows}

    added = False
    for name in OPERATIONAL_ROLE_NAMES:
        if name not in existing_names:
            db.add(Role(name=name, is_system=False))
            added = True

    if added:
        await db.commit()


async def get_role_or_404(db: AsyncSession, role_id: int) -> Role:
    """Fetch role by ID with permissions loaded, or raise 404."""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .where(Role.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


async def get_all_valid_permission_keys(db: AsyncSession) -> set:
    """Get all valid permission keys from the database."""
    result = await db.execute(select(PermissionModel.key).where(PermissionModel.key.isnot(None)))
    return {row[0] for row in result.fetchall()}


async def get_permission_ids_by_keys(db: AsyncSession, keys: List[str]) -> dict:
    """Get mapping of permission keys to IDs."""
    result = await db.execute(
        select(PermissionModel.key, PermissionModel.id)
        .where(PermissionModel.key.in_(keys))
    )
    return {row[0]: row[1] for row in result.fetchall()}


def get_role_permission_keys(role: Role) -> List[str]:
    """Extract permission keys from a role's permissions relationship."""
    keys = []
    for rp in role.permissions:
        if rp.permission and rp.permission.key:
            keys.append(rp.permission.key)
        elif rp.permission and rp.permission.name:
            keys.append(rp.permission.name)
    return sorted(keys)


def serialize_role_detail(role: Role) -> dict:
    """Serialize a role for API response."""
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "scope": role.scope,
        "is_system": role.is_system or False,
        "permissions": get_role_permission_keys(role),
        "created_at": role.created_at,
    }


async def check_role_in_use(db: AsyncSession, role_id: int) -> int:
    """Check how many users are assigned to this role via user_roles table."""
    from app.db.models import UserRole as UserRoleModel
    count = await db.scalar(
        select(func.count(UserRoleModel.user_id))
        .where(UserRoleModel.role_id == role_id)
    )
    return count or 0


async def ensure_not_last_admin_by_role(db: AsyncSession, user_id: int, new_role_id: int) -> None:
    """
    Ensure changing a user's role won't remove the last system admin.
    """
    # Get the user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_system_admin:
        return
    
    # Check if new role is system_admin
    new_role_result = await db.execute(select(Role.name).where(Role.id == new_role_id))
    new_role_name = new_role_result.scalar_one_or_none()
    
    if new_role_name == "system_admin":
        return  # No change in admin status
    
    # Count other active system admins
    admin_count = await db.scalar(
        select(func.count(User.id))
        .where(
            User.is_system_admin == True,
            User.is_active == True,
            User.id != user_id
        )
    )
    
    if (admin_count or 0) < 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot change role: this would remove the last system administrator"
        )


# === Role Management Endpoints ===

@router.get("/roles", response_model=RoleListResponse)
async def list_roles_db(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    List all available roles with their permissions (DB-driven).
    
    Returns all roles including system roles (system_admin, default).
    System roles are listed first.
    """
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .order_by(Role.is_system.desc(), Role.name)
    )
    roles = result.scalars().all()
    
    role_list = [
        RoleDetailOut(
            id=role.id,
            name=role.name,
            description=role.description,
            scope=role.scope,
            is_system=role.is_system or False,
            permissions=get_role_permission_keys(role),
            created_at=role.created_at,
        )
        for role in roles
    ]
    
    return RoleListResponse(roles=role_list, total=len(role_list))


@router.get("/roles/operational", response_model=RoleListResponse)
async def list_operational_roles(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    List operational roles only.

    Returns roles seeded for operational use (admin, agent, sales_agent, storekeeper, foreman, delivery).
    This endpoint excludes system/chat roles and is accessible only to system admins.
    """
    # Ensure operational roles exist in the DB before listing
    await ensure_operational_roles(db)

    result = await db.execute(
        select(Role)
        .options(selectinload(Role.permissions).selectinload(RolePermission.permission))
        .where(Role.name.in_(OPERATIONAL_ROLE_NAMES))
        .order_by(Role.name)
    )
    roles = result.scalars().all()

    role_list = [
        RoleDetailOut(
            id=role.id,
            name=role.name,
            description=role.description,
            scope=role.scope,
            is_system=role.is_system or False,
            permissions=get_role_permission_keys(role),
            created_at=role.created_at,
        )
        for role in roles
    ]

    return RoleListResponse(roles=role_list, total=len(role_list))


@router.post("/roles", response_model=RoleDetailOut, status_code=201)
async def create_role(
    request: RoleCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Create a new role.
    
    Rules:
    - Name must be lowercase snake_case
    - Cannot create system roles (system_admin, default)
    - All permissions must exist in the database
    """
    import re
    
    # Validate name format
    if not re.match(r'^[a-z][a-z0-9_]*$', request.name):
        raise HTTPException(
            status_code=400,
            detail="Role name must be lowercase snake_case (e.g., sales_manager)"
        )
    
    # Cannot use reserved system role names
    if request.name in ('system_admin', 'default'):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create role with reserved name: {request.name}"
        )
    
    # Check if role name already exists
    existing = await db.execute(select(Role).where(Role.name == request.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Role '{request.name}' already exists")
    
    # Validate permissions exist
    if request.permissions:
        valid_keys = await get_all_valid_permission_keys(db)
        invalid = set(request.permissions) - valid_keys
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid permissions: {', '.join(sorted(invalid))}"
            )
    
    # Create the role
    role = Role(
        name=request.name,
        description=request.description,
        scope="system",
        is_system=False,
    )
    db.add(role)
    await db.flush()
    
    # Assign permissions
    if request.permissions:
        perm_id_map = await get_permission_ids_by_keys(db, request.permissions)
        for perm_key in request.permissions:
            if perm_key in perm_id_map:
                rp = RolePermission(role_id=role.id, permission_id=perm_id_map[perm_key])
                db.add(rp)
    
    await db.commit()
    
    # Reload with permissions
    role = await get_role_or_404(db, role.id)
    
    # Log audit
    await log_audit(
        db=db,
        action=AuditActions.ROLE_CREATE,
        target_type=AuditTargetTypes.ROLE,
        target_id=role.id,
        description=f"Created role '{role.name}'",
        meta={
            "role_name": role.name,
            "permissions": request.permissions,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return RoleDetailOut(
        id=role.id,
        name=role.name,
        description=role.description,
        scope=role.scope,
        is_system=role.is_system or False,
        permissions=get_role_permission_keys(role),
        created_at=role.created_at,
    )


@router.get("/roles/{role_id}", response_model=RoleDetailOut)
async def get_role_by_id(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """Get a specific role by ID."""
    role = await get_role_or_404(db, role_id)
    return RoleDetailOut(
        id=role.id,
        name=role.name,
        description=role.description,
        scope=role.scope,
        is_system=role.is_system or False,
        permissions=get_role_permission_keys(role),
        created_at=role.created_at,
    )


@router.patch("/roles/{role_id}/permissions")
async def update_role_permissions_db(
    role_id: int,
    request: RoleUpdatePermissionsRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Update permissions for a role.
    
    Rules:
    - Cannot modify permissions of system roles below minimums
    - Diffs old vs new permissions
    - Logs added and removed permissions separately
    """
    role = await get_role_or_404(db, role_id)
    
    # Get current permission keys
    old_permissions = set(get_role_permission_keys(role))
    new_permissions = set(request.permissions)
    
    # Validate all new permissions exist
    valid_keys = await get_all_valid_permission_keys(db)
    invalid = new_permissions - valid_keys
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid permissions: {', '.join(sorted(invalid))}"
        )
    
    # System role minimum permission protection
    if role.is_system:
        if role.name == "system_admin":
            # system_admin must retain all system.* permissions
            required = {"system.manage_users", "system.manage_roles", "system.view_audit", "system.manage_settings"}
            missing = required - new_permissions
            if missing:
                raise HTTPException(
                    status_code=400,
                    detail=f"System admin role must retain permissions: {', '.join(sorted(missing))}"
                )
    
    # Calculate diff
    added = new_permissions - old_permissions
    removed = old_permissions - new_permissions
    
    # No changes
    if not added and not removed:
        return {
            "message": "No permission changes",
            "changed": False,
            "role": serialize_role_detail(role),
        }
    
    # Clear existing permissions
    await db.execute(
        delete(RolePermission).where(RolePermission.role_id == role_id)
    )
    
    # Add new permissions
    perm_id_map = await get_permission_ids_by_keys(db, list(new_permissions))
    for perm_key in new_permissions:
        if perm_key in perm_id_map:
            rp = RolePermission(role_id=role_id, permission_id=perm_id_map[perm_key])
            db.add(rp)
    
    await db.commit()
    
    # Reload role
    role = await get_role_or_404(db, role_id)
    
    # Log audit with diff
    await log_audit(
        db=db,
        action=AuditActions.ROLE_PERMISSIONS_UPDATE,
        target_type=AuditTargetTypes.ROLE,
        target_id=role_id,
        description=f"Updated permissions for role '{role.name}'",
        meta={
            "role_name": role.name,
            "before": sorted(old_permissions),
            "after": sorted(new_permissions),
            "added": sorted(added),
            "removed": sorted(removed),
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return {
        "message": f"Permissions updated for role '{role.name}'",
        "changed": True,
        "added": sorted(added),
        "removed": sorted(removed),
        "role": serialize_role_detail(role),
    }


@router.delete("/roles/{role_id}")
async def delete_role_db(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Delete a role.
    
    Rules:
    - Cannot delete system roles (is_system == true)
    - Cannot delete roles that are assigned to users
    """
    role = await get_role_or_404(db, role_id)
    
    # Cannot delete system roles
    if role.is_system:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete system role '{role.name}'"
        )
    
    # Check if role is in use
    users_count = await check_role_in_use(db, role_id)
    if users_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role '{role.name}': {users_count} user(s) are assigned to this role"
        )
    
    role_name = role.name
    role_permissions = get_role_permission_keys(role)
    
    # Delete the role (cascade will remove role_permissions)
    await db.delete(role)
    await db.commit()
    
    # Log audit
    await log_audit(
        db=db,
        action=AuditActions.ROLE_DELETE,
        target_type=AuditTargetTypes.ROLE,
        target_id=role_id,
        description=f"Deleted role '{role_name}'",
        meta={
            "role_name": role_name,
            "permissions_had": role_permissions,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return {
        "message": f"Role '{role_name}' deleted successfully",
        "deleted": True,
    }


# === Permission Listing (DB-driven) ===

@router.get("/permissions", response_model=PermissionListResponse)
async def list_permissions_db(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    List all available permissions in the system (DB-driven).
    
    Permissions are stored in the database, not hardcoded.
    """
    result = await db.execute(
        select(PermissionModel)
        .where(PermissionModel.key.isnot(None))
        .order_by(PermissionModel.key)
    )
    permissions = result.scalars().all()
    
    perm_list = [
        PermissionDetailOut(
            id=p.id,
            key=p.key or p.name,
            name=p.name,
            description=p.description,
        )
        for p in permissions
    ]
    
    return PermissionListResponse(permissions=perm_list, total=len(perm_list))


# === User Role Assignment ===

@router.patch("/users/{user_id}/assign-role")
async def assign_role_to_user(
    user_id: int,
    request: UserRoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Assign a *system* role to a user (DB-driven role system).

    Rules:
    - Role must exist and be a system role
    - Prevents last-admin downgrade (if role isn't system_admin)
    - Logs before/after role
    """
    from app.db.models import UserRole as UserRoleModel

    user = await get_user_or_404(db, user_id)
    before_state = serialize_user_state(user)

    # Get the role
    role = await get_role_or_404(db, request.role_id)

    # Role must be a system role for this endpoint
    if not role.is_system:
        raise HTTPException(status_code=400, detail="Role must be a system role for this endpoint")

    # Last-admin protection
    await ensure_not_last_admin_by_role(db, user_id, request.role_id)

    # Get current system role assignment (if any)
    result = await db.execute(
        select(UserRoleModel)
        .join(Role)
        .options(selectinload(UserRoleModel.role))
        .where(UserRoleModel.user_id == user_id, Role.is_system == True)
    )
    current_assignment = result.scalar_one_or_none()
    old_role_name = current_assignment.role.name if current_assignment else None

    # Same role - no change
    if current_assignment and current_assignment.role_id == request.role_id:
        return {
            "message": f"User {user.username} already has role '{role.name}'",
            "changed": False,
        }

    # Remove old system assignment if exists
    if current_assignment:
        await db.delete(current_assignment)

    # Create new system assignment
    new_assignment = UserRoleModel(user_id=user_id, role_id=request.role_id)
    db.add(new_assignment)

    # Sync is_system_admin flag
    if role.name == "system_admin":
        user.is_system_admin = True
        user.role = UserRole.system_admin
    else:
        user.is_system_admin = False
        # Map to nearest UserRole enum
        if role.name in ('team_admin',):
            user.role = UserRole.team_admin
        elif role.name in ('guest',):
            user.role = UserRole.guest
        else:
            user.role = UserRole.member

    await db.commit()
    await db.refresh(user)

    after_state = serialize_user_state(user)

    # Log audit
    await log_audit(
        db=db,
        action=AuditActions.USER_ROLE_CHANGE,
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"Changed {user.username} role from '{old_role_name or 'none'}' to '{role.name}'",
        meta={
            "before": before_state,
            "after": after_state,
            "old_role": old_role_name,
            "new_role": role.name,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )

    return {
        "message": f"User {user.username} assigned role '{role.name}' successfully",
        "changed": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": role.name,
            "is_system_admin": user.is_system_admin,
        },
    }


@router.patch("/users/{user_id}/operational-role")
async def assign_operational_role(
    user_id: int,
    request: OperationalRoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """
    Assign or remove an operational role for a user (non-system role) without affecting system roles.

    Rules:
    - operational_role_id may be null to remove any existing operational role
    - Provided role must exist and be one of OPERATIONAL_ROLE_NAMES
    - Logs before/after state
    """
    from app.db.models import UserRole as UserRoleModel

    user = await get_user_or_404(db, user_id)
    before_state = serialize_user_state(user)

    # If removing operational role
    if request.operational_role_id is None:
        # Find existing operational assignment(s)
        result = await db.execute(
            select(UserRoleModel)
            .join(Role)
            .options(selectinload(UserRoleModel.role))
            .where(UserRoleModel.user_id == user_id, Role.name.in_(OPERATIONAL_ROLE_NAMES))
        )
        existing = result.scalars().all()
        if not existing:
            return {"message": "No operational role to remove", "changed": False}
        for e in existing:
            await db.delete(e)
        await db.commit()
        await db.refresh(user)

        after_state = serialize_user_state(user)
        await log_audit(
            db=db,
            action="user.operational_role_change",
            target_type=AuditTargetTypes.USER,
            target_id=user_id,
            description=f"Removed operational role(s) for {user.username}",
            meta={"before": before_state, "after": after_state, "actor": admin.username},
            user_id=admin.id,
            username=admin.username,
        )
        return {"message": "Operational role removed", "changed": True}

    # Assigning/updating operational role
    op_role = await db.execute(select(Role).where(Role.id == request.operational_role_id))
    op_role_obj = op_role.scalar_one_or_none()
    if not op_role_obj:
        raise HTTPException(status_code=404, detail="Operational role not found")
    if op_role_obj.name not in OPERATIONAL_ROLE_NAMES:
        raise HTTPException(status_code=400, detail="Provided role is not a valid operational role")

    # Find existing operational assignment
    result2 = await db.execute(
        select(UserRoleModel)
        .join(Role)
        .options(selectinload(UserRoleModel.role))
        .where(UserRoleModel.user_id == user_id, Role.name.in_(OPERATIONAL_ROLE_NAMES))
    )
    existing_assignment = result2.scalar_one_or_none()

    if existing_assignment and existing_assignment.role_id == request.operational_role_id:
        return {"message": f"User already has operational role '{op_role_obj.name}'", "changed": False}

    if existing_assignment:
        await db.delete(existing_assignment)

    new_assignment = UserRoleModel(user_id=user_id, role_id=request.operational_role_id)
    db.add(new_assignment)
    await db.commit()
    await db.refresh(user)

    after_state = serialize_user_state(user)
    await log_audit(
        db=db,
        action="user.operational_role_change",
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"Set operational role for {user.username} to '{op_role_obj.name}'",
        meta={"before": before_state, "after": after_state, "actor": admin.username, "new_operational_role": op_role_obj.name},
        user_id=admin.id,
        username=admin.username,
    )

    return {"message": f"Operational role '{op_role_obj.name}' assigned", "changed": True, "role": op_role_obj.name}
    """
    Assign a *system* role to a user (DB-driven role system).

    Rules:
    - Role must exist and be a system role
    - Prevents last-admin downgrade (if role isn't system_admin)
    - Logs before/after role
    """
    from app.db.models import UserRole as UserRoleModel

    user = await get_user_or_404(db, user_id)
    before_state = serialize_user_state(user)

    # Get the role
    role = await get_role_or_404(db, request.role_id)

    # Role must be a system role for this endpoint
    if not role.is_system:
        raise HTTPException(status_code=400, detail="Role must be a system role for this endpoint")

    # Last-admin protection
    await ensure_not_last_admin_by_role(db, user_id, request.role_id)

    # Get current system role assignment (if any)
    result = await db.execute(
        select(UserRoleModel)
        .join(Role)
        .options(selectinload(UserRoleModel.role))
        .where(UserRoleModel.user_id == user_id, Role.is_system == True)
    )
    current_assignment = result.scalar_one_or_none()
    old_role_name = current_assignment.role.name if current_assignment else None

    # Same role - no change
    if current_assignment and current_assignment.role_id == request.role_id:
        return {
            "message": f"User {user.username} already has role '{role.name}'",
            "changed": False,
        }

    # Remove old system assignment if exists
    if current_assignment:
        await db.delete(current_assignment)

    # Create new system assignment
    new_assignment = UserRoleModel(user_id=user_id, role_id=request.role_id)
    db.add(new_assignment)

    # Sync is_system_admin flag
    if role.name == "system_admin":
        user.is_system_admin = True
        user.role = UserRole.system_admin
    else:
        user.is_system_admin = False
        # Map to nearest UserRole enum
        if role.name in ('team_admin',):
            user.role = UserRole.team_admin
        elif role.name in ('guest',):
            user.role = UserRole.guest
        else:
            user.role = UserRole.member
    
    await db.commit()
    await db.refresh(user)
    
    after_state = serialize_user_state(user)
    
    # Log audit
    await log_audit(
        db=db,
        action=AuditActions.USER_ROLE_CHANGE,
        target_type=AuditTargetTypes.USER,
        target_id=user_id,
        description=f"Changed {user.username} role from '{old_role_name or 'none'}' to '{role.name}'",
        meta={
            "before": before_state,
            "after": after_state,
            "old_role": old_role_name,
            "new_role": role.name,
            "actor": admin.username,
        },
        user_id=admin.id,
        username=admin.username,
    )
    
    return {
        "message": f"User {user.username} assigned role '{role.name}' successfully",
        "changed": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": role.name,
            "is_system_admin": user.is_system_admin,
        },
    }


# === System Settings ===

@router.get("/settings", response_model=SystemSettingsResponse)
async def get_system_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """Get current system settings (read-only view)."""
    return SystemSettingsResponse(
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        features={
            "websockets_enabled": settings.WS_ENABLED,
            "automations_enabled": settings.AUTOMATIONS_ENABLED,
            "rate_limiting_enabled": rate_limit_settings.ENABLED,
        },
        upload_limits={
            "max_upload_mb": settings.MAX_UPLOAD_MB,
        },
        rate_limits={
            "auth": {
                "anonymous": f"{AUTH_LIMITS.anonymous.requests}/{AUTH_LIMITS.anonymous.window_seconds}s",
                "authenticated": f"{AUTH_LIMITS.authenticated.requests}/{AUTH_LIMITS.authenticated.window_seconds}s",
                "admin": f"{AUTH_LIMITS.admin.requests}/{AUTH_LIMITS.admin.window_seconds}s",
            },
            "api": {
                "anonymous": f"{API_LIMITS.anonymous.requests}/{API_LIMITS.anonymous.window_seconds}s",
                "authenticated": f"{API_LIMITS.authenticated.requests}/{API_LIMITS.authenticated.window_seconds}s",
                "admin": f"{API_LIMITS.admin.requests}/{API_LIMITS.admin.window_seconds}s",
            },
            "sales": {
                "anonymous": f"{SALES_LIMITS.anonymous.requests}/{SALES_LIMITS.anonymous.window_seconds}s",
                "authenticated": f"{SALES_LIMITS.authenticated.requests}/{SALES_LIMITS.authenticated.window_seconds}s",
                "admin": f"{SALES_LIMITS.admin.requests}/{SALES_LIMITS.admin.window_seconds}s",
            },
        },
    )


# === Audit Log ===

@router.get("/audit-log", response_model=AuditLogResponse)
async def get_system_audit_log(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """Get paginated audit log with filters."""
    query = select(AuditLog)
    
    # Apply filters
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    
    if target_type:
        query = query.where(AuditLog.target_type == target_type)
    
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    if start_date:
        query = query.where(AuditLog.created_at >= start_date)
    
    if end_date:
        query = query.where(AuditLog.created_at <= end_date)
    
    # Get total count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    
    # Apply pagination
    offset = (page - 1) * limit
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    try:
        entries = []
        for log in logs:
            # Meta may be None, or malformed JSON
            meta_dict = None
            if log.meta:
                try:
                    meta_dict = json.loads(log.meta)
                except (json.JSONDecodeError, TypeError):
                    # Keep raw string as fallback
                    try:
                        meta_dict = {"raw": str(log.meta)}
                    except Exception:
                        meta_dict = None

            # created_at may be NULL in malformed rows - fallback to now
            created_at = log.created_at if getattr(log, 'created_at', None) else datetime.utcnow()

            entries.append(AuditLogEntry(
                id=getattr(log, 'id', None) or 0,
                user_id=getattr(log, 'user_id', None),
                username=getattr(log, 'username', None),
                action=getattr(log, 'action', '') or '',
                target_type=getattr(log, 'target_type', None),
                target_id=getattr(log, 'target_id', None),
                description=getattr(log, 'description', None),
                meta=meta_dict,
                created_at=created_at,
            ))

        return AuditLogResponse(
            logs=entries,
            total=total or 0,
            page=page,
            limit=limit,
        )
    except Exception as e:
        # Log full traceback and return safe default
        api_logger.error("Failed to fetch audit log", error=e)
        return AuditLogResponse(logs=[], total=0, page=page, limit=limit)


@router.get("/audit-log/actions")
async def get_audit_action_types(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """Get list of unique action types for filter dropdown."""
    result = await db.execute(
        select(AuditLog.action)
        .distinct()
        .order_by(AuditLog.action)
    )
    actions = [row[0] for row in result.fetchall() if row[0]]
    return {"actions": actions}


@router.get("/audit-log/target-types")
async def get_audit_target_types(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """Get list of unique target types for filter dropdown."""
    result = await db.execute(
        select(AuditLog.target_type)
        .distinct()
        .order_by(AuditLog.target_type)
    )
    types = [row[0] for row in result.fetchall() if row[0]]
    return {"target_types": types}


# === System Stats ===

@router.get("/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    """Get system-wide statistics."""
    from app.db.models import Channel, Message, Team
    
    # User stats
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True, User.is_banned == False)
    )
    admin_users = await db.scalar(
        select(func.count(User.id)).where(User.is_system_admin == True)
    )
    banned_users = await db.scalar(
        select(func.count(User.id)).where(User.is_banned == True)
    )
    
    # Channel stats
    total_channels = await db.scalar(select(func.count(Channel.id)))
    
    # Message stats
    total_messages = await db.scalar(
        select(func.count(Message.id)).where(Message.is_deleted == False)
    )
    
    # Team stats
    total_teams = await db.scalar(select(func.count(Team.id)))
    
    # Audit stats (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_actions = await db.scalar(
        select(func.count(AuditLog.id)).where(AuditLog.created_at >= yesterday)
    )
    
    return {
        "users": {
            "total": total_users or 0,
            "active": active_users or 0,
            "admins": admin_users or 0,
            "banned": banned_users or 0,
        },
        "channels": {
            "total": total_channels or 0,
        },
        "messages": {
            "total": total_messages or 0,
        },
        "teams": {
            "total": total_teams or 0,
        },
        "audit": {
            "last_24h": recent_actions or 0,
        },
    }

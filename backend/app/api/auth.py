from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from app.db.database import get_db
from app.db.models import User, UserOperationalRole
from app.core.security import verify_password, get_password_hash, create_access_token
# Use the lightweight JWT dependency from security and resolve to DB User via app.api.deps.get_current_user
from app.api.deps import get_current_user
# Use lower-level JWT dependency here to catch and handle unexpected errors during user resolution
from app.core.security import get_current_user as jwt_get_current_user
from app.core.rate_limiter import check_rate_limit, get_client_ip
from app.core.rate_limit_config import AUTH_LIMITS, rate_limit_settings

router = APIRouter()


# === Rate Limiting for Auth Endpoints ===
# Note: The RateLimitMiddleware already applies IP-based rate limiting.
# This dependency provides additional per-endpoint tracking for auth abuse detection.
# Both use the same rate bucket so there's no double-counting.

async def auth_rate_limit(request: Request):
    """
    Rate limiting marker for auth endpoints (login/register).
    The actual limiting is done by RateLimitMiddleware.
    This dependency is kept for clarity and potential future per-action tracking.
    """
    # Rate limiting is handled by RateLimitMiddleware
    # This is a no-op but documents that auth endpoints are rate limited
    pass


class LoginRequest(BaseModel):
    identifier: str  # username or email
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    display_name: Optional[str] = None
    role: Optional[str] = None  # Business role: agent, storekeeper, delivery, foreman, customer


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    display_name: Optional[str]
    avatar_url: Optional[str]
    is_system_admin: bool

    class Config:
        from_attributes = True


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(auth_rate_limit),
):
    # Find user by username or email
    query = select(User).where(
        (User.username == request.identifier) | (User.email == request.identifier)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    # Check if this is first login (before updating timestamp)
    from datetime import datetime, timezone as dt_timezone
    is_first_login = user.last_login_at is None
    
    # Update last login timestamp
    user.last_login_at = datetime.now(dt_timezone.utc)
    db.add(user)
    await db.commit()
    
    # Phase 8.4.4: Include is_system_admin in JWT for rate limit decisions
    access_token = create_access_token(data={
        "sub": str(user.id), 
        "username": user.username,
        "is_system_admin": user.is_system_admin,
    })
    
    # FRESH DB query for operational_roles from user_operational_roles table (source of truth)
    logger = logging.getLogger(__name__)
    roles_result = await db.execute(
        select(UserOperationalRole.role)
        .where(UserOperationalRole.user_id == user.id)
    )
    operational_roles = [r[0] for r in roles_result]
    
    logger.info(
        "[AUTH_LOGIN] user_id=%s operational_roles=%s",
        user.id,
        operational_roles
    )

    # Fetch legacy operational role assignment (if any) for back-compat fields
    from app.db.models import UserRole as UserRoleModel, Role
    from app.api.system import OPERATIONAL_ROLE_NAMES

    op_result = await db.execute(
        select(UserRoleModel)
        .join(Role)
        .options(selectinload(UserRoleModel.role))
        .where(UserRoleModel.user_id == user.id, Role.name.in_(OPERATIONAL_ROLE_NAMES))
    )
    op_assignment = op_result.scalar_one_or_none()
    op_role_id = op_assignment.role_id if op_assignment else None
    op_role_name = op_assignment.role.name if op_assignment else None

    return TokenResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_system_admin": user.is_system_admin,
            "role": user.role,
            "operational_role_id": op_role_id,
            "operational_role_name": op_role_name,
            "operational_roles": operational_roles,  # Fresh from user_operational_roles table
            "must_change_password": user.must_change_password or False,
            "is_first_login": is_first_login,
        }
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(auth_rate_limit),
):
    # Check if username exists
    query = select(User).where(User.username == request.username)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    
    # Check if email exists
    query = select(User).where(User.email == request.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Validate role if provided
    valid_roles = {'agent', 'storekeeper', 'delivery', 'foreman', 'customer', 'member', 'guest'}
    user_role = request.role if request.role in valid_roles else 'member'
    
    # Create user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        display_name=request.display_name or request.username,
        role=user_role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # DEV-only: auto-onboard new user to all demo channels
    from app.permissions.demo_onboarding import maybe_onboard_demo_user
    await maybe_onboard_demo_user(user.id, db)

    # Ensure the user is a member of the default 'general' channel so they have a readable channel after first login.
    # Prefer existing channel 'general', otherwise create it as public.
    # Use models to find or create the 'general' channel
    from app.db.models import Channel, ChannelMember, ChannelType, Role, ChannelRoleAssignment
    from app.permissions.roles import ChannelRole

    result = await db.execute(select(Channel).where(Channel.name == 'general'))
    general_channel = result.scalar_one_or_none()
    if not general_channel:
        general_channel = Channel(name='general', display_name='General', description='General discussion', type=ChannelType.public.value)
        db.add(general_channel)
        await db.commit()
        await db.refresh(general_channel)

    # Add membership if not exists
    result = await db.execute(select(ChannelMember).where(ChannelMember.user_id == user.id, ChannelMember.channel_id == general_channel.id))
    membership = result.scalar_one_or_none()
    if not membership:
        new_membership = ChannelMember(user_id=user.id, channel_id=general_channel.id)
        db.add(new_membership)
        await db.commit()

    # Add ChannelRoleAssignment (member role) for the general channel if not exists
    # This ensures new users have read permissions on the general channel
    result = await db.execute(
        select(Role).where(Role.name == ChannelRole.MEMBER.value, Role.scope == "channel")
    )
    member_role = result.scalar_one_or_none()
    
    if member_role:
        result = await db.execute(
            select(ChannelRoleAssignment).where(
                ChannelRoleAssignment.user_id == user.id,
                ChannelRoleAssignment.channel_id == general_channel.id,
                ChannelRoleAssignment.role_id == member_role.id
            )
        )
        if not result.scalar_one_or_none():
            assignment = ChannelRoleAssignment(
                user_id=user.id,
                channel_id=general_channel.id,
                role_id=member_role.id
            )
            db.add(assignment)
            await db.commit()

    # Phase 8.4.4: Include is_system_admin in JWT for rate limit decisions
    access_token = create_access_token(data={
        "sub": str(user.id), 
        "username": user.username,
        "is_system_admin": user.is_system_admin,
    })

    # FRESH DB query for operational_roles from user_operational_roles table (source of truth)
    # For new users, this will be empty but we query for consistency
    logger = logging.getLogger(__name__)
    roles_result = await db.execute(
        select(UserOperationalRole.role)
        .where(UserOperationalRole.user_id == user.id)
    )
    operational_roles = [r[0] for r in roles_result]
    
    logger.info(
        "[AUTH_REGISTER] user_id=%s operational_roles=%s",
        user.id,
        operational_roles
    )

    # Fetch legacy operational role assignment (if any) - keep consistent with /login
    from app.db.models import UserRole as UserRoleModel, Role
    from app.api.system import OPERATIONAL_ROLE_NAMES

    op_result = await db.execute(
        select(UserRoleModel)
        .join(Role)
        .options(selectinload(UserRoleModel.role))
        .where(UserRoleModel.user_id == user.id, Role.name.in_(OPERATIONAL_ROLE_NAMES))
    )
    op_assignment = op_result.scalar_one_or_none()
    op_role_id = op_assignment.role_id if op_assignment else None
    op_role_name = op_assignment.role.name if op_assignment else None

    return TokenResponse(
        access_token=access_token,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "avatar_url": user.avatar_url,
            "is_system_admin": user.is_system_admin,
            "role": user.role,
            "operational_role_id": op_role_id,
            "operational_role_name": op_role_name,
            "operational_roles": operational_roles,  # Fresh from user_operational_roles table
            "must_change_password": user.must_change_password or False,
            "is_first_login": True,  # New registrations are always first login
        }
    )


def serialize_user(user: User, operational_roles: list[str] = None) -> dict:
    """Return API-safe serialized user dict including operational role fields.

    operational_roles MUST be passed in from fresh DB query - do NOT cache.
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_system_admin": user.is_system_admin,
        "role": user.role,
        "operational_role_id": getattr(user, 'operational_role_id', None),
        "operational_role_name": getattr(user, 'operational_role_name', None),
        "operational_roles": operational_roles or [],  # Fresh from user_operational_roles table
        "must_change_password": getattr(user, 'must_change_password', False) or False,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


@router.get("/me")
async def me(
    current_user_data: dict = Depends(jwt_get_current_user),
    db: AsyncSession = Depends(get_db),
):
    logger = logging.getLogger(__name__)
    
    # Use lower-level JWT dependency above and resolve to DB User here so we can
    # catch unexpected errors that might occur while resolving DB user or serializing.
    try:
        current_user = await get_current_user(current_user_data, db)
        
        # FRESH DB query for operational_roles - do NOT use cached/JWT data
        roles_result = await db.execute(
            select(UserOperationalRole.role)
            .where(UserOperationalRole.user_id == current_user.id)
        )
        operational_roles = [r[0] for r in roles_result]
        
        # Debug log to verify roles are being fetched correctly
        logger.info(
            "[AUTH_ME] user_id=%s operational_roles=%s",
            current_user.id,
            operational_roles
        )
        
        # If the user is a system administrator, ensure they behave as an operational admin
        # at runtime (without modifying the DB). This grants them operational 'admin' role
        # for UI and permission resolution across services.
        if getattr(current_user, 'is_system_admin', False):
            from app.db.models import Role
            role_result = await db.execute(select(Role).where(Role.name == 'admin'))
            admin_role = role_result.scalar_one_or_none()
            current_user.operational_role_name = 'admin'
            current_user.operational_role_id = admin_role.id if admin_role else None
        
        return serialize_user(current_user, operational_roles)
    except HTTPException:
        # Re-raise standard HTTP exceptions (e.g., 404/401 from get_current_user)
        raise
    except Exception as e:
        from app.core.logging import api_logger
        api_logger.error(
            "/api/auth/me failed during user resolution",
            error=str(e),
            exc_type=type(e).__name__,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")


@router.post("/logout")
async def logout():
    # For JWT, logout is handled client-side by removing the token
    return {"message": "Successfully logged out"}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Change user's password.
    Requires current password verification.
    Clears must_change_password flag and updates password_changed_at.
    """
    from datetime import datetime, timezone as dt_timezone
    
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    
    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    current_user.must_change_password = False
    current_user.password_changed_at = datetime.now(dt_timezone.utc)
    
    db.add(current_user)
    await db.commit()
    
    return {
        "message": "Password changed successfully",
        "must_change_password": False,
    }
